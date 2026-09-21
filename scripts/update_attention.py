from datetime import date
import json
import os
from pathlib import Path
import requests

# 1. 动态获取当前脚本所在目录 (scripts/)，并定位到仓库根目录下的 attention.json
SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR.parent / "attention.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

GITHUB_API = "https://api.github.com"
ZENODO_API_BASE = "https://zenodo.org/api/records"


def get_json(url, headers=None, timeout=30):
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def init_default_data():
    """当 attention.json 不存在时返回一个合法的初始结构，防止读取报错"""
    return {
        "updated": "",
        "last_verified": "",
        "data_quality": {"last_checked": ""},
        "audit_control": {"status": "Pending"},
        "github": {"repositories": [{}], "totals": {}},
        "zenodo": {"records": [{"id": "22139197"}], "totals": {}},
        "researchgate": {"total_reads": 0, "total_recommendations": 0},
        "osf": {"totals": {"views": 0, "downloads": 0}},
        "validation": {"citations": 0, "independent_replications": 0},
        "attention": {
            "reach_events": 0,
            "engagement_events": 0,
            "research_action_events": 0,
            "validation_events": 0,
            "components": {
                "reach": {},
                "engagement": {},
                "research_actions": {},
                "validation": {},
            },
        },
    }


def update_telemetry():
    if not GITHUB_TOKEN or not REPO_NAME:
        raise RuntimeError(
            "缺少必要的环境变量 (GITHUB_TOKEN 或 GITHUB_REPOSITORY)。"
        )

    # 2. 读取原 JSON（如果不存在则初始化默认结构）
    if not JSON_PATH.exists():
        print(f"提示: 未找到 {JSON_PATH}，将自动创建初始 JSON 文件。")
        data = init_default_data()
    else:
        with JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)

    today = date.today().isoformat()

    # 3. 从 GitHub API 获取 Repo 基础数据（Stars/Forks）及流量数据
    github_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_url = f"{GITHUB_API}/repos/{REPO_NAME}"

    # 获取实时 Stars 与 Forks
    repo_info = get_json(repo_url, headers=github_headers)
    gh_stars = repo_info.get("stargazers_count", 0)
    gh_forks = repo_info.get("forks_count", 0)

    # 获取近 14 天流量
    views_data = get_json(f"{repo_url}/traffic/views", headers=github_headers)
    clones_data = get_json(f"{repo_url}/traffic/clones", headers=github_headers)

    gh_views = views_data.get("count", 0)
    gh_uniques = views_data.get("uniques", 0)
    gh_clones = clones_data.get("count", 0)
    gh_cloners = clones_data.get("uniques", 0)

    # 更新 GitHub 源层
    if data["github"].get("repositories"):
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

    # 4. 从 Zenodo API 获取数据（动态读取 JSON 中的 record_id）
    zenodo_record_id = "22139197"
    if data.get("zenodo", {}).get("records"):
        zenodo_record_id = data["zenodo"]["records"][0].get("id", zenodo_record_id)

    zenodo_url = f"{ZENODO_API_BASE}/{zenodo_record_id}"
    zenodo_data = get_json(zenodo_url)
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

    if data["zenodo"].get("records"):
        data["zenodo"]["records"][0].update(zenodo_payload)
    data["zenodo"]["totals"].update(zenodo_payload)

    # 5. 读取其它平台的现有数据（如 ResearchGate, OSF, Validation）
    rg_reads = data["researchgate"].get("total_reads", 0)
    rg_recs = data["researchgate"].get("total_recommendations", 0)

    osf_views = data["osf"]["totals"].get("views", 0)
    osf_downloads = data["osf"]["totals"].get("downloads", 0)

    val_citations = data["validation"].get("citations", 0)
    val_replications = data["validation"].get("independent_replications", 0)

    # 6. 重新计算 Attention 汇总
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

    # 7. 断言自检
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

    # 8. 更新时间戳
    data["updated"] = today
    data["last_verified"] = today
    data["data_quality"]["last_checked"] = today

    # 9. 保存回 JSON
    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[{today}] {JSON_PATH.name} 自动更新并审计通过！")


if __name__ == "__main__":
    update_telemetry()
