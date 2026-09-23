#!/usr/bin/env python3
"""
scripts/update_attention.py
Automated Telemetry Fetcher for scottsun.com (Schema v3.0)

Polls GitHub REST API and Zenodo REST API to automatically update
`data/attention.json` metrics and recalculate aggregate attention events.
"""

import json
import os
import sys
import datetime
import requests

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "attention.json")

def fetch_zenodo_metrics(record_id: str) -> dict | None:
    """Fetch record stats from Zenodo REST API."""
    url = f"https://zenodo.org/api/records/{record_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            stats = response.json().get("stats", {})
            return {
                "total_views": stats.get("views", 0),
                "unique_views": stats.get("unique_views", 0),
                "total_downloads": stats.get("downloads", 0),
                "unique_downloads": stats.get("unique_downloads", 0)
            }
        else:
            print(f"[Warning] Zenodo API returned status code {response.status_code} for record {record_id}")
    except Exception as e:
        print(f"[Warning] Failed to connect to Zenodo API: {e}")
    return None


def fetch_github_metrics(repo_url: str, token: str) -> dict | None:
    """Fetch engagement and traffic metrics from GitHub REST API."""
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[-2], parts[-1]

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    metrics = {
        "stars": 0,
        "forks": 0,
        "views": 0,
        "unique_visitors": 0,
        "clones": 0,
        "unique_cloners": 0
    }

    # 1. Fetch Repository General Info (Stars, Forks)
    repo_api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        res = requests.get(repo_api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            repo_data = res.json()
            metrics["stars"] = repo_data.get("stargazers_count", 0)
            metrics["forks"] = repo_data.get("forks_count", 0)
        else:
            print(f"[Warning] GitHub Repo API returned status {res.status_code} for {owner}/{repo}")
    except Exception as e:
        print(f"[Warning] Failed to fetch GitHub repo info for {owner}/{repo}: {e}")

    # 2. Fetch Traffic Views (Rolling 14 Days)
    views_api_url = f"https://api.github.com/repos/{owner}/{repo}/traffic/views"
    try:
        res = requests.get(views_api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            views_data = res.json()
            metrics["views"] = views_data.get("count", 0)
            metrics["unique_visitors"] = views_data.get("uniques", 0)
    except Exception as e:
        print(f"[Warning] Failed to fetch GitHub traffic views for {owner}/{repo}: {e}")

    # 3. Fetch Traffic Clones (Rolling 14 Days)
    clones_api_url = f"https://api.github.com/repos/{owner}/{repo}/traffic/clones"
    try:
        res = requests.get(clones_api_url, headers=headers, timeout=10)
        if res.status_code == 200:
            clones_data = res.json()
            metrics["clones"] = clones_data.get("count", 0)
            metrics["unique_cloners"] = clones_data.get("uniques", 0)
    except Exception as e:
        print(f"[Warning] Failed to fetch GitHub traffic clones for {owner}/{repo}: {e}")

    return metrics


def main():
    data_path = os.path.abspath(DATA_PATH)
    if not os.path.exists(data_path):
        print(f"[Error] Target dataset file not found at: {data_path}")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    github_token = os.environ.get("GITHUB_TOKEN", "")

    # -------------------------------------------------------------
    # 0. Defensive Key Initialisation
    # -------------------------------------------------------------
    if "zenodo" not in data:
        data["zenodo"] = {}
    if "github" not in data:
        data["github"] = {}
    if "attention" not in data:
        data["attention"] = {}

    # -------------------------------------------------------------
    # 1. Update Zenodo Metrics
    # -------------------------------------------------------------
    zenodo_records = data.get("zenodo", {}).get("records", [])
    total_z_views = 0
    total_z_uviews = 0
    total_z_downloads = 0
    total_z_udownloads = 0

    for rec in zenodo_records:
        rec_id = rec.get("id")
        if rec_id:
            z_stats = fetch_zenodo_metrics(rec_id)
            if z_stats:
                rec["total_views"] = z_stats["total_views"]
                rec["unique_views"] = z_stats["unique_views"]
                rec["total_downloads"] = z_stats["total_downloads"]
                rec["unique_downloads"] = z_stats["unique_downloads"]

        total_z_views += rec.get("total_views", 0)
        total_z_uviews += rec.get("unique_views", 0)
        total_z_downloads += rec.get("total_downloads", 0)
        total_z_udownloads += rec.get("unique_downloads", 0)

    # 如果没有 records 明细，保留现有 totals 的打底数据
    existing_z_totals = data.get("zenodo", {}).get("totals", {})
    data["zenodo"]["totals"] = {
        "total_views": max(total_z_views, existing_z_totals.get("total_views", 0)),
        "unique_views": max(total_z_uviews, existing_z_totals.get("unique_views", 0)),
        "total_downloads": max(total_z_downloads, existing_z_totals.get("total_downloads", 0)),
        "unique_downloads": max(total_z_udownloads, existing_z_totals.get("unique_downloads", 0))
    }

    # -------------------------------------------------------------
    # 2. Update GitHub Metrics (If Token Available)
    # -------------------------------------------------------------
    gh_repos = data.get("github", {}).get("repositories", [])
    total_gh_views = 0
    total_gh_uvisitors = 0
    total_gh_clones = 0
    total_gh_ucloners = 0
    total_gh_forks = 0
    total_gh_stars = 0

    for repo in gh_repos:
        repo_url = repo.get("url")
        if github_token and repo_url:
            gh_stats = fetch_github_metrics(repo_url, github_token)
            if gh_stats:
                repo.setdefault("traffic", {})
                repo.setdefault("engagement", {})
                repo["traffic"]["views"] = gh_stats["views"]
                repo["traffic"]["unique_visitors"] = gh_stats["unique_visitors"]
                repo["traffic"]["clones"] = gh_stats["clones"]
                repo["traffic"]["unique_cloners"] = gh_stats["unique_cloners"]
                repo["engagement"]["forks"] = gh_stats["forks"]
                repo["engagement"]["stars"] = gh_stats["stars"]

        total_gh_views += repo.get("traffic", {}).get("views", 0)
        total_gh_uvisitors += repo.get("traffic", {}).get("unique_visitors", 0)
        total_gh_clones += repo.get("traffic", {}).get("clones", 0)
        total_gh_ucloners += repo.get("traffic", {}).get("unique_cloners", 0)
        total_gh_forks += repo.get("engagement", {}).get("forks", 0)
        total_gh_stars += repo.get("engagement", {}).get("stars", 0)

    existing_gh_totals = data.get("github", {}).get("totals", {})
    data["github"]["totals"] = {
        "views": max(total_gh_views, existing_gh_totals.get("views", 0)),
        "unique_visitors": max(total_gh_uvisitors, existing_gh_totals.get("unique_visitors", 0)),
        "clones": max(total_gh_clones, existing_gh_totals.get("clones", 0)),
        "unique_cloners": max(total_gh_ucloners, existing_gh_totals.get("unique_cloners", 0)),
        "forks": max(total_gh_forks, existing_gh_totals.get("forks", 0)),
        "stars": max(total_gh_stars, existing_gh_totals.get("stars", 0))
    }

    # -------------------------------------------------------------
    # 3. Recalculate Aggregate Attention Events
    # -------------------------------------------------------------
    rg_reads = data.get("researchgate", {}).get("total_reads", 0)
    rg_recs = data.get("researchgate", {}).get("total_recommendations", 0)
    citations = data.get("google_scholar", {}).get("citations_total", 0)

    z_tot_views = data["zenodo"]["totals"]["total_views"]
    z_tot_downloads = data["zenodo"]["totals"]["total_downloads"]
    gh_tot_views = data["github"]["totals"]["views"]
    gh_tot_stars = data["github"]["totals"]["stars"]
    gh_tot_forks = data["github"]["totals"]["forks"]
    gh_tot_clones = data["github"]["totals"]["clones"]

    reach = gh_tot_views + z_tot_views + rg_reads
    engagement = gh_tot_stars + gh_tot_forks + rg_recs + citations
    research_actions = z_tot_downloads + gh_tot_clones
    academic_attention = citations

    data["attention"]["reach_events"] = reach
    data["attention"]["engagement_events"] = engagement
    data["attention"]["research_action_events"] = research_actions
    data["attention"]["academic_attention_events"] = academic_attention

    # -------------------------------------------------------------
    # 4. Update Audit Metadata (With KeyError Guards)
    # -------------------------------------------------------------
    data["updated"] = today
    data["last_verified"] = today
    
    if "data_quality" not in data:
        data["data_quality"] = {}
    data["data_quality"]["last_checked"] = today

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[Success] Telemetry metrics successfully updated and saved to {DATA_PATH} ({today})")


if __name__ == "__main__":
    main()
