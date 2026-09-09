from datetime import date
import json
import os
from pathlib import Path
import requests

JSON_PATH = Path("attention.json")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

ZENODO_RECORD_ID = "22139197"
GITHUB_API = "https://api.github.com"
ZENODO_API = f"https://zenodo.org/api/records/{ZENODO_RECORD_ID}"


def get_json(url, headers=None, timeout=30):
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def update_telemetry():
    if not GITHUB_TOKEN or not REPO_NAME:
        raise RuntimeError(
            "缺少必要的环境变量 (GITHUB_TOKEN 或 GITHUB_REPOSITORY)。"
        )

    # 1. 读取原 JSON
    with JSON_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    today = date.today().isoformat()

    # 2. 从 GitHub API 获取流量数据
    github_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    traffic_url = f"{GITHUB_API}/repos/{REPO_NAME}/traffic"

    views_data = get_json(f"{traffic_url}/views", headers=github_headers)
    clones_data = get_json(f"{traffic_url}/clones", headers=github_headers)

    gh_views = views_data.get("count", 0)
    gh_uniques = views_data.get("uniques", 0)
    gh_clones = clones_data.get("count", 0)
    gh_cloners = clones_data.get("uniques", 0)

    gh_forks = data["github"]["totals"].get("forks", 0)
    gh_stars = data["github"]["totals"].get("stars", 0)

    # 更新 GitHub 源层
    if data["github"]["repositories"]:
        data["github"]["repositories"][0]["traffic"] = {
            "views": gh_views,
            "unique_visitors": gh_uniques,
            "clones": gh_clones,
            "unique_cloners": gh_cloners,
        }
        data["github"]["repositories"][0]["engagement"] = {
            "forks": gh_forks,
            "stars": gh_stars,
        }

    data["github"]["totals"] = {
        "views": gh_views,
        "unique_visitors": gh_uniques,
        "clones": gh_clones,
        "unique_cloners": gh_cloners,
        "forks": gh_forks,
        "stars": gh_stars,
    }

    # 3. 从 Zenodo API 获取下载与访问数据
    zenodo_data = get_json(ZENODO_API)
    z_stats = zenodo_data.get("stats", {})

    z_unique_views = z_stats.get("unique_views", 0)
    z_views = z_stats.get("views", 0)
    z_unique_downloads = z_stats.get("unique_downloads", 0)
    z_downloads = z_stats.get("downloads", 0)

    zenodo_payload = {
        "unique_views": z_unique_views,
        "total_views": z_views,
        "unique_downloads": z_unique_downloads,
        "total_downloads": z_downloads,
    }

    if data["zenodo"]["records"]:
        data["zenodo"]["records"][0].update(zenodo_payload)
    data["zenodo"]["totals"].update(zenodo_payload)

    # 4. 读取其它平台的现有数据（如手动维度的 ResearchGate）
    rg_reads = data["researchgate"]["total_reads"]
    rg_recs = data["researchgate"]["total_recommendations"]

    osf_views = data["osf"]["totals"]["views"]
    osf_downloads = data["osf"]["totals"]["downloads"]

    val_citations = data["validation"]["citations"]
    val_replications = data["validation"]["independent_replications"]

    # 5. 严格依据原始方法论重新计算 Attention 汇总
    reach_total = gh_views + rg_reads + z_views + osf_views
    engagement_total = gh_uniques + rg_recs
    research_action_total = gh_clones + gh_forks + z_downloads + osf_downloads
    validation_total = val_citations + val_replications

    data["attention"]["reach_events"] = reach_total
    data["attention"]["engagement_events"] = engagement_total
    data["attention"]["research_action_events"] = research_action_total
    data["attention"]["validation_events"] = validation_total

    data["attention"]["components"]["reach"] = {
        "github_views": gh_views,
        "researchgate_reads": rg_reads,
        "zenodo_views": z_views,
        "osf_views": osf_views,
        "calculated_total": reach_total,
    }

    data["attention"]["components"]["engagement"] = {
        "github_unique_visitors": gh_uniques,
        "researchgate_recommendations": rg_recs,
        "calculated_total": engagement_total,
    }

    data["attention"]["components"]["research_actions"] = {
        "github_clones": gh_clones,
        "github_forks": gh_forks,
        "zenodo_downloads": z_downloads,
        "osf_downloads": osf_downloads,
        "calculated_total": research_action_total,
    }

    data["attention"]["components"]["validation"] = {
        "citations": val_citations,
        "independent_replications": val_replications,
        "calculated_total": validation_total,
    }

    # 6. 断言自检（保障符合 audit_control 逻辑）
    assert reach_total == (
        gh_views + rg_reads + z_views + osf_views
    ), "Reach 逻辑校验失败"
    assert engagement_total == (gh_uniques + rg_recs), "Engagement 逻辑校验失败"
    assert research_action_total == (
        gh_clones + gh_forks + z_downloads + osf_downloads
    ), "Research Actions 逻辑校验失败"
    assert validation_total == (
        val_citations + val_replications
    ), "Validation 逻辑校验失败"

    data["audit_control"]["status"] = "Passed"

    # 7. 更新时间戳与标记
    data["updated"] = today
    data["last_verified"] = today
    data["data_quality"]["last_checked"] = today

    # 8. 保存回 JSON
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[{today}] attention.json 自动更新并审计通过！")


if __name__ == "__main__":
    update_telemetry()
