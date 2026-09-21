from datetime import date
import json
import os
from pathlib import Path
import requests

# --------------------------------------------------
# Repository layout
#
# root/
# ├── data/
# │   └── attention.json
# ├── scripts/
# │   └── update_attention.py
# └── attention.json (legacy)
# --------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

DATA_DIR = ROOT / "data"
JSON_PATH = DATA_DIR / "attention.json"

LEGACY_JSON_PATH = ROOT / "attention.json"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")

GITHUB_API = "https://api.github.com"
ZENODO_API_BASE = "https://zenodo.org/api/records"


def get_json(url, headers=None, timeout=30):
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def init_default_data():
    return {
        "schema_version": "1.1",
        "updated": "",
        "last_verified": "",
        "data_quality": {
            "last_checked": ""
        },
        "audit_control": {
            "status": "Pending"
        },
        "github": {
            "repositories": [{}],
            "totals": {}
        },
        "zenodo": {
            "records": [
                {
                    "id": "22139197",
                    "doi": "10.5281/zenodo.22139197"
                }
            ],
            "totals": {}
        },
        "researchgate": {
            "total_reads": 0,
            "total_recommendations": 0
        },
        "osf": {
            "totals": {
                "views": 0,
                "downloads": 0
            }
        },
        "validation": {
            "citations": 0,
            "independent_replications": 0
        },
        "attention": {
            "reach_events": 0,
            "engagement_events": 0,
            "research_action_events": 0,
            "validation_events": 0,
            "academic_attention_events": 0,
            "components": {
                "reach": {},
                "engagement": {},
                "research_actions": {},
                "validation": {}
            }
        }
    }


def load_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if JSON_PATH.exists():
        with JSON_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    if LEGACY_JSON_PATH.exists():
        with LEGACY_JSON_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)

        print(
            f"[MIGRATION] Using legacy file "
            f"{LEGACY_JSON_PATH}"
        )
        return data

    print(
        f"[INIT] Creating new telemetry file: "
        f"{JSON_PATH}"
    )

    return init_default_data()


def update_telemetry():

    if not GITHUB_TOKEN or not REPO_NAME:
        raise RuntimeError(
            "缺少必要环境变量 "
            "(GITHUB_TOKEN 或 GITHUB_REPOSITORY)"
        )

    data = load_data()

    today = date.today().isoformat()

    github_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    repo_url = f"{GITHUB_API}/repos/{REPO_NAME}"

    # --------------------------------------------------
    # GitHub metrics
    # --------------------------------------------------

    repo_info = get_json(
        repo_url,
        headers=github_headers
    )

    gh_stars = repo_info.get(
        "stargazers_count",
        0
    )

    gh_forks = repo_info.get(
        "forks_count",
        0
    )

    views_data = get_json(
        f"{repo_url}/traffic/views",
        headers=github_headers
    )

    clones_data = get_json(
        f"{repo_url}/traffic/clones",
        headers=github_headers
    )

    gh_views = views_data.get("count", 0)
    gh_uniques = views_data.get("uniques", 0)

    gh_clones = clones_data.get("count", 0)
    gh_cloners = clones_data.get("uniques", 0)

    data.setdefault("github", {})

    repos = data["github"].setdefault(
        "repositories",
        []
    )

    if not repos:
        repos.append({})

    repos[0]["traffic"] = {
        "views": gh_views,
        "unique_visitors": gh_uniques,
        "clones": gh_clones,
        "unique_cloners": gh_cloners,
    }

    repos[0]["engagement"] = {
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

    # --------------------------------------------------
    # Zenodo metrics
    # --------------------------------------------------

    z_views = 0
    z_downloads = 0

    try:

        zenodo_record_id = "22139197"

        if data.get("zenodo", {}).get("records"):
            zenodo_record_id = (
                data["zenodo"]["records"][0]
                .get("id", zenodo_record_id)
            )

        zenodo_url = (
            f"{ZENODO_API_BASE}/{zenodo_record_id}"
        )

        zenodo_data = get_json(zenodo_url)

        z_stats = zenodo_data.get(
            "stats",
            {}
        )

        z_unique_views = z_stats.get(
            "unique_views",
            0
        )

        z_views = z_stats.get(
            "views",
            0
        )

        z_unique_downloads = z_stats.get(
            "unique_downloads",
            0
        )

        z_downloads = z_stats.get(
            "downloads",
            0
        )

        zenodo_payload = {
            "unique_views": z_unique_views,
            "total_views": z_views,
            "unique_downloads": z_unique_downloads,
            "total_downloads": z_downloads,
        }

        if data["zenodo"].get("records"):
            data["zenodo"]["records"][0].update(
                zenodo_payload
            )

        data["zenodo"]["totals"].update(
            zenodo_payload
        )

    except Exception as exc:

        print(
            f"[WARN] Zenodo API failed: {exc}"
        )

        z_views = (
            data.get("zenodo", {})
            .get("totals", {})
            .get("total_views", 0)
        )

        z_downloads = (
            data.get("zenodo", {})
            .get("totals", {})
            .get("total_downloads", 0)
        )

    # --------------------------------------------------
    # Additional sources
    # --------------------------------------------------

    rg_reads = data["researchgate"].get(
        "total_reads",
        0
    )

    rg_recs = data["researchgate"].get(
        "total_recommendations",
        0
    )

    osf_views = data["osf"]["totals"].get(
        "views",
        0
    )

    osf_downloads = data["osf"]["totals"].get(
        "downloads",
        0
    )

    val_citations = data["validation"].get(
        "citations",
        0
    )

    val_replications = data["validation"].get(
        "independent_replications",
        0
    )

    # --------------------------------------------------
    # Calculations
    # --------------------------------------------------

    reach_total = (
        gh_views +
        rg_reads +
        z_views +
        osf_views
    )

    engagement_total = (
        gh_uniques +
        rg_recs
    )

    research_action_total = (
        gh_clones +
        gh_forks +
        z_downloads +
        osf_downloads
    )

    validation_total = (
        val_citations +
        val_replications
    )

    data["attention"]["reach_events"] = reach_total

    data["attention"]["engagement_events"] = (
        engagement_total
    )

    data["attention"]["research_action_events"] = (
        research_action_total
    )

    data["attention"]["validation_events"] = (
        validation_total
    )

    data["attention"]["academic_attention_events"] = (
        validation_total
    )

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

    # --------------------------------------------------
    # Audit
    # --------------------------------------------------

    assert reach_total == (
        gh_views +
        rg_reads +
        z_views +
        osf_views
    )

    assert engagement_total == (
        gh_uniques +
        rg_recs
    )

    assert research_action_total == (
        gh_clones +
        gh_forks +
        z_downloads +
        osf_downloads
    )

    assert validation_total == (
        val_citations +
        val_replications
    )

    data["audit_control"]["status"] = "Passed"

    data["updated"] = today
    data["last_verified"] = today
    data["data_quality"]["last_checked"] = today

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with JSON_PATH.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

        f.write("\n")

    print(
        f"[{today}] "
        f"{JSON_PATH} updated successfully."
    )


if __name__ == "__main__":
    update_telemetry()
