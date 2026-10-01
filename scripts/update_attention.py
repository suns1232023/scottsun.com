#!/usr/bin/env python3
"""
scripts/update_attention.py
Automated Telemetry Updater for scottsun.com (Schema v3.0)

Polls the GitHub REST API and Zenodo REST API to update
`data/attention.json` and recalculate aggregate attention events.

Aggregate definitions (Schema v3.0):
  reach_events           = github_views + zenodo_total_views + rg_reads
  engagement_events      = github_unique_visitors + rg_recommendations
  research_action_events = zenodo_total_downloads + github_clones
  academic_attention     = google_scholar_citations

Note: citations are counted only in academic_attention_events, not in
engagement_events, to avoid double-counting across dimensions.
"""

import json
import os
import sys
import datetime
import requests

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "attention.json")


def fetch_zenodo_metrics(record_id: str) -> dict | None:
    """Fetch record stats from the Zenodo REST API.

    Returns a dict with total_views, unique_views, total_downloads,
    unique_downloads, or None on failure.
    """
    url = f"https://zenodo.org/api/records/{record_id}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            stats = response.json().get("stats", {})
            return {
                "total_views":      stats.get("views", 0),
                "unique_views":     stats.get("unique_views", 0),
                "total_downloads":  stats.get("downloads", 0),
                "unique_downloads": stats.get("unique_downloads", 0),
            }
        print(
            f"[Warning] Zenodo API returned status {response.status_code} "
            f"for record {record_id}"
        )
    except Exception as exc:
        print(f"[Warning] Failed to connect to Zenodo API: {exc}")
    return None


def fetch_github_metrics(repo_url: str, token: str) -> dict | None:
    """Fetch traffic and engagement metrics from the GitHub REST API.

    Returns a dict with views, unique_visitors, clones, unique_cloners,
    stars, forks, or None if the repo URL is malformed.
    """
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[-2], parts[-1]

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    metrics = {
        "stars": 0, "forks": 0,
        "views": 0, "unique_visitors": 0,
        "clones": 0, "unique_cloners": 0,
    }

    # 1. Repository info (stars, forks)
    try:
        res = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers, timeout=10,
        )
        if res.status_code == 200:
            repo_data = res.json()
            metrics["stars"] = repo_data.get("stargazers_count", 0)
            metrics["forks"] = repo_data.get("forks_count", 0)
        else:
            print(
                f"[Warning] GitHub Repo API returned status {res.status_code} "
                f"for {owner}/{repo}"
            )
    except Exception as exc:
        print(f"[Warning] Failed to fetch GitHub repo info for {owner}/{repo}: {exc}")

    # 2. Traffic views (rolling 14-day window)
    try:
        res = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/traffic/views",
            headers=headers, timeout=10,
        )
        if res.status_code == 200:
            views_data = res.json()
            metrics["views"]           = views_data.get("count", 0)
            metrics["unique_visitors"] = views_data.get("uniques", 0)
    except Exception as exc:
        print(
            f"[Warning] Failed to fetch GitHub traffic views "
            f"for {owner}/{repo}: {exc}"
        )

    # 3. Traffic clones (rolling 14-day window)
    try:
        res = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/traffic/clones",
            headers=headers, timeout=10,
        )
        if res.status_code == 200:
            clones_data = res.json()
            metrics["clones"]         = clones_data.get("count", 0)
            metrics["unique_cloners"] = clones_data.get("uniques", 0)
    except Exception as exc:
        print(
            f"[Warning] Failed to fetch GitHub traffic clones "
            f"for {owner}/{repo}: {exc}"
        )

    return metrics


def main() -> None:
    data_path = os.path.abspath(DATA_PATH)
    if not os.path.exists(data_path):
        print(f"[Error] Target dataset file not found at: {data_path}")
        sys.exit(1)

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    today        = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    github_token = os.environ.get("GITHUB_TOKEN", "")

    # ------------------------------------------------------------------
    # 0. Defensive key initialisation
    # ------------------------------------------------------------------
    data.setdefault("zenodo",    {})
    data.setdefault("github",    {})
    data.setdefault("attention", {})

    # ------------------------------------------------------------------
    # 1. Update Zenodo totals from per-record entries
    # ------------------------------------------------------------------
    zenodo_records   = data.get("zenodo", {}).get("records", [])
    seen_record_ids  = set()   # guard against duplicate DOIs
    total_z_views    = 0
    total_z_uviews   = 0
    total_z_downloads  = 0
    total_z_udownloads = 0

    for rec in zenodo_records:
        rec_id = rec.get("id")
        if not rec_id:
            continue

        z_stats = fetch_zenodo_metrics(rec_id)
        if z_stats:
            rec["total_views"]      = z_stats["total_views"]
            rec["unique_views"]     = z_stats["unique_views"]
            rec["total_downloads"]  = z_stats["total_downloads"]
            rec["unique_downloads"] = z_stats["unique_downloads"]

        # Only count each unique Zenodo record once in the totals
        if rec_id not in seen_record_ids:
            seen_record_ids.add(rec_id)
            total_z_views      += rec.get("total_views", 0)
            total_z_uviews     += rec.get("unique_views", 0)
            total_z_downloads  += rec.get("total_downloads", 0)
            total_z_udownloads += rec.get("unique_downloads", 0)

    # Monotonic preservation: never let totals decrease
    existing_z = data.get("zenodo", {}).get("totals", {})
    data["zenodo"]["totals"] = {
        "total_views":      max(total_z_views,      existing_z.get("total_views", 0)),
        "unique_views":     max(total_z_uviews,     existing_z.get("unique_views", 0)),
        "total_downloads":  max(total_z_downloads,  existing_z.get("total_downloads", 0)),
        "unique_downloads": max(total_z_udownloads, existing_z.get("unique_downloads", 0)),
    }

    # ------------------------------------------------------------------
    # 2. Update GitHub metrics (requires GITHUB_TOKEN)
    # ------------------------------------------------------------------
    gh_repos         = data.get("github", {}).get("repositories", [])
    total_gh_views   = 0
    total_gh_uniq    = 0
    total_gh_clones  = 0
    total_gh_uclone  = 0
    total_gh_forks   = 0
    total_gh_stars   = 0

    for repo in gh_repos:
        repo_url = repo.get("url")
        if github_token and repo_url:
            gh_stats = fetch_github_metrics(repo_url, github_token)
            if gh_stats:
                repo.setdefault("traffic",    {})
                repo.setdefault("engagement", {})
                repo["traffic"]["views"]           = gh_stats["views"]
                repo["traffic"]["unique_visitors"] = gh_stats["unique_visitors"]
                repo["traffic"]["clones"]          = gh_stats["clones"]
                repo["traffic"]["unique_cloners"]  = gh_stats["unique_cloners"]
                repo["engagement"]["forks"]        = gh_stats["forks"]
                repo["engagement"]["stars"]        = gh_stats["stars"]

        total_gh_views  += repo.get("traffic",    {}).get("views",           0)
        total_gh_uniq   += repo.get("traffic",    {}).get("unique_visitors", 0)
        total_gh_clones += repo.get("traffic",    {}).get("clones",          0)
        total_gh_uclone += repo.get("traffic",    {}).get("unique_cloners",  0)
        total_gh_forks  += repo.get("engagement", {}).get("forks",           0)
        total_gh_stars  += repo.get("engagement", {}).get("stars",           0)

    # Monotonic preservation
    existing_gh = data.get("github", {}).get("totals", {})
    data["github"]["totals"] = {
        "views":           max(total_gh_views,  existing_gh.get("views",           0)),
        "unique_visitors": max(total_gh_uniq,   existing_gh.get("unique_visitors", 0)),
        "clones":          max(total_gh_clones, existing_gh.get("clones",          0)),
        "unique_cloners":  max(total_gh_uclone, existing_gh.get("unique_cloners",  0)),
        "forks":           max(total_gh_forks,  existing_gh.get("forks",           0)),
        "stars":           max(total_gh_stars,  existing_gh.get("stars",           0)),
    }

    # ------------------------------------------------------------------
    # 3. Recalculate aggregate attention events
    #
    # Definitions (Schema v3.0):
    #   reach           = passive exposure across all platforms
    #   engagement      = active platform interactions (visits + recommendations)
    #   research_actions= download / clone / fork actions
    #   academic_attention = formal scholarly citations
    # ------------------------------------------------------------------
    rg_reads  = data.get("researchgate",   {}).get("total_reads",        0)
    rg_recs   = data.get("researchgate",   {}).get("total_recommendations", 0)
    citations = data.get("google_scholar", {}).get("citations_total",    0)

    z_views     = data["zenodo"]["totals"]["total_views"]
    z_downloads = data["zenodo"]["totals"]["total_downloads"]
    gh_views    = data["github"]["totals"]["views"]
    gh_uniq     = data["github"]["totals"]["unique_visitors"]
    gh_clones   = data["github"]["totals"]["clones"]

    # reach: all passive views/reads across platforms
    reach = gh_views + z_views + rg_reads

    # engagement: distinct active interactions (unique visitors + recommendations)
    # Note: citations are NOT included here; they are counted in academic_attention.
    engagement = gh_uniq + rg_recs

    # research_actions: download and clone actions
    research_actions = z_downloads + gh_clones

    # academic_attention: formal scholarly citations only
    academic_attention = citations

    data["attention"]["reach_events"]           = reach
    data["attention"]["engagement_events"]      = engagement
    data["attention"]["research_action_events"] = research_actions
    data["attention"]["academic_attention_events"] = academic_attention

    # ------------------------------------------------------------------
    # 4. Update audit metadata
    # ------------------------------------------------------------------
    data["updated"]      = today
    data["last_verified"] = today
    data.setdefault("data_quality", {})
    data["data_quality"]["last_checked"] = today

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"[Success] Telemetry updated and saved to {DATA_PATH} ({today})\n"
        f"  reach={reach}, engagement={engagement}, "
        f"research_actions={research_actions}, academic_attention={academic_attention}"
    )


if __name__ == "__main__":
    main()
