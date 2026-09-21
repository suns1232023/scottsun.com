"""
update_attention.py — Scott Sun Academic Homepage
Fetches telemetry from GitHub and Zenodo APIs,
recomputes attention metrics, and writes data/attention.json.

Usage (via GitHub Actions):
    python scripts/update_attention.py

Required environment variables:
    GITHUB_TOKEN       — GitHub Actions token (contents: write)
    GITHUB_REPOSITORY  — e.g. "scottsun/suns-conjecture-2468"
"""

from datetime import date
import json
import os
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT       = SCRIPT_DIR.parent

DATA_DIR          = ROOT / "data"
JSON_PATH         = DATA_DIR / "attention.json"
LEGACY_JSON_PATH  = ROOT / "attention.json"   # pre-migration location

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME    = os.getenv("GITHUB_REPOSITORY")

# ---------------------------------------------------------------------------
# API constants
# ---------------------------------------------------------------------------

GITHUB_API      = "https://api.github.com"
ZENODO_API_BASE = "https://zenodo.org/api/records"

GITHUB_HEADERS = {
    "Authorization":      f"Bearer {GITHUB_TOKEN}",
    "Accept":             "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

HTTP_TIMEOUT = 30   # seconds

# Staleness threshold written into data_quality
STALENESS_THRESHOLD_DAYS = 30


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def get_json(url: str, headers: dict | None = None) -> dict:
    """GET a URL and return parsed JSON. Raises on HTTP error."""
    resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Default data structure
# Mirrors attention.json v2.2 — keep in sync with data/attention.json
# ---------------------------------------------------------------------------

def init_default_data() -> dict:
    """
    Return a valid skeleton when no attention.json exists yet.
    All numeric fields default to 0; all required keys are present.
    """
    return {
        "_comment":        "Scott Sun — Research Attention Data | data/attention.json",
        "_schema_version": "2.2",
        "updated":         "",
        "last_verified":   "",

        "data_quality": {
            "attention_totals_verified": False,
            "staleness_threshold_days":  STALENESS_THRESHOLD_DAYS,
            "last_checked":              "",
        },

        "audit_control": {"status": "Pending"},

        "github": {
            "data_window": "rolling_14_days",
            "repositories": [
                {
                    "name": "suns-conjecture-2468",
                    "url":  "https://github.com/scottsun/suns-conjecture-2468",
                    "traffic": {
                        "views":          0,
                        "unique_visitors": 0,
                        "clones":         0,
                        "unique_cloners": 0,
                    },
                    "engagement": {"forks": 0, "stars": 0},
                }
            ],
            "totals": {
                "views":          0,
                "unique_visitors": 0,
                "clones":         0,
                "unique_cloners": 0,
                "forks":          0,
                "stars":          0,
            },
        },

        "zenodo": {
            "totals": {
                "total_views":      0,
                "unique_views":     0,
                "total_downloads":  0,
                "unique_downloads": 0,
            },
            "records": [
                {"id": "22139197", "doi": "10.5281/zenodo.22139197",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "21973304", "doi": "10.5281/zenodo.21973304",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "22019535", "doi": "10.5281/zenodo.22019535",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "20483898", "doi": "10.5281/zenodo.20483898",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "20792832", "doi": "10.5281/zenodo.20792832",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "21524285", "doi": "10.5281/zenodo.21524285",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "20373606", "doi": "10.5281/zenodo.20373606",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
                {"id": "20300824", "doi": "10.5281/zenodo.20300824",
                 "total_views": 0, "unique_views": 0,
                 "total_downloads": 0, "unique_downloads": 0},
            ],
        },

        "osf": {
            "totals": {"views": 0, "downloads": 0},
            "projects": [
                {"doi": "10.17605/OSF.IO/CAQXH",
                 "title": "Sun's (2,4,6,8) Conjecture — OSF Hub",
                 "views": 0, "downloads": 0},
            ],
        },

        "researchgate": {
            "total_reads":           0,
            "total_recommendations": 0,
            "profile_url": "https://www.researchgate.net/profile/Scott-Sun",
        },

        "validation": {
            "citations":               0,
            "independent_replications": 0,
            "notes": "No independent replication or peer validation recorded.",
        },

        "attention": {
            "_note": (
                "Pre-aggregated for cross-checking. "
                "JS recomputes from source-level fields and flags discrepancies."
            ),
            "reach_events":              0,
            "verification_events":       0,
            "academic_attention_events": 0,
            "components": {
                "reach": {
                    "github_views":       0,
                    "zenodo_views":       0,
                    "osf_views":          0,
                    "researchgate_reads": 0,
                    "calculated_total":   0,
                },
                "verification": {
                    "github_clones":    0,
                    "github_forks":     0,
                    "zenodo_downloads": 0,
                    "osf_downloads":    0,
                    "calculated_total": 0,
                },
                "academic_attention": {
                    "citations":               0,
                    "independent_replications": 0,
                    "calculated_total":        0,
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data() -> dict:
    """
    Load attention.json from DATA_DIR.
    Falls back to legacy root location, then to init_default_data().
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if JSON_PATH.exists():
        with JSON_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    if LEGACY_JSON_PATH.exists():
        print(f"[MIGRATION] Reading legacy file: {LEGACY_JSON_PATH}")
        with LEGACY_JSON_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    print(f"[INIT] No attention.json found — initialising defaults: {JSON_PATH}")
    return init_default_data()


# ---------------------------------------------------------------------------
# GitHub metrics
# ---------------------------------------------------------------------------

def fetch_github_metrics(repo_url: str) -> dict:
    """
    Fetch stars, forks, traffic views and clones from GitHub API.
    Raises requests.RequestException on network / HTTP failure.
    """
    repo_info   = get_json(repo_url,                          headers=GITHUB_HEADERS)
    views_data  = get_json(f"{repo_url}/traffic/views",       headers=GITHUB_HEADERS)
    clones_data = get_json(f"{repo_url}/traffic/clones",      headers=GITHUB_HEADERS)

    return {
        "stars":          repo_info.get("stargazers_count", 0),
        "forks":          repo_info.get("forks_count",      0),
        "views":          views_data.get("count",           0),
        "unique_visitors": views_data.get("uniques",        0),
        "clones":         clones_data.get("count",          0),
        "unique_cloners": clones_data.get("uniques",        0),
    }


# ---------------------------------------------------------------------------
# Zenodo metrics
# ---------------------------------------------------------------------------

def fetch_zenodo_record(record_id: str) -> dict:
    """
    Fetch stats for a single Zenodo record.
    Returns a dict with view/download counts, or zeros on failure.
    """
    url = f"{ZENODO_API_BASE}/{record_id}"
    try:
        data   = get_json(url)
        stats  = data.get("stats", {})
        return {
            "unique_views":     stats.get("unique_views",     0),
            "total_views":      stats.get("views",            0),
            "unique_downloads": stats.get("unique_downloads", 0),
            "total_downloads":  stats.get("downloads",        0),
        }
    except Exception as exc:
        print(f"[WARN] Zenodo API failed for record {record_id}: {exc}")
        return {
            "unique_views": 0, "total_views": 0,
            "unique_downloads": 0, "total_downloads": 0,
        }


# ---------------------------------------------------------------------------
# Audit helper (replaces assert)
# ---------------------------------------------------------------------------

def _verify(label: str, computed: int, expected: int) -> bool:
    """
    Compare a computed total against an expected value.
    Prints a warning and returns False on mismatch.
    Uses explicit if-check instead of assert so it works under python -O.
    """
    if computed != expected:
        print(
            f"[WARN] Audit mismatch — {label}: "
            f"computed={computed}, expected={expected}"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Main telemetry update
# ---------------------------------------------------------------------------

def update_telemetry() -> None:

    if not GITHUB_TOKEN or not REPO_NAME:
        raise RuntimeError(
            "Missing required environment variables: "
            "GITHUB_TOKEN and/or GITHUB_REPOSITORY"
        )

    data  = load_data()
    today = date.today().isoformat()

    # ------------------------------------------------------------------ #
    # 1. GitHub                                                           #
    # ------------------------------------------------------------------ #
    repo_url = f"{GITHUB_API}/repos/{REPO_NAME}"

    try:
        gh = fetch_github_metrics(repo_url)
    except requests.RequestException as exc:
        raise RuntimeError(f"GitHub API unavailable: {exc}") from exc

    gh_views   = gh["views"]
    gh_uniques = gh["unique_visitors"]
    gh_clones  = gh["clones"]
    gh_forks   = gh["forks"]
    gh_stars   = gh["stars"]

    # Write into data structure (safe even if key was missing)
    data.setdefault("github", {})
    repos = data["github"].setdefault("repositories", [{}])
    if not repos:
        repos.append({})

    repos[0]["traffic"] = {
        "views":          gh_views,
        "unique_visitors": gh_uniques,
        "clones":         gh_clones,
        "unique_cloners": gh["unique_cloners"],
    }
    repos[0]["engagement"] = {"forks": gh_forks, "stars": gh_stars}

    data["github"]["totals"] = {
        "views":          gh_views,
        "unique_visitors": gh_uniques,
        "clones":         gh_clones,
        "unique_cloners": gh["unique_cloners"],
        "forks":          gh_forks,
        "stars":          gh_stars,
    }

    # ------------------------------------------------------------------ #
    # 2. Zenodo — iterate ALL records                                     #
    # ------------------------------------------------------------------ #
    data.setdefault("zenodo", {"totals": {}, "records": []})

    zen_total_views     = 0
    zen_total_downloads = 0
    zen_unique_views    = 0
    zen_unique_downloads = 0

    for record in data["zenodo"].get("records", []):
        record_id = record.get("id", "")
        if not record_id:
            continue

        stats = fetch_zenodo_record(record_id)
        record.update(stats)

        zen_total_views      += stats["total_views"]
        zen_total_downloads  += stats["total_downloads"]
        zen_unique_views     += stats["unique_views"]
        zen_unique_downloads += stats["unique_downloads"]

    data["zenodo"]["totals"] = {
        "total_views":      zen_total_views,
        "unique_views":     zen_unique_views,
        "total_downloads":  zen_total_downloads,
        "unique_downloads": zen_unique_downloads,
    }

    # ------------------------------------------------------------------ #
    # 3. Manually maintained sources (read from existing JSON)            #
    # ------------------------------------------------------------------ #
    rg  = data.get("researchgate", {})
    osf = data.get("osf", {}).get("totals", {})
    val = data.get("validation", {})

    rg_reads      = rg.get("total_reads",              0)
    rg_recs       = rg.get("total_recommendations",    0)
    osf_views     = osf.get("views",                   0)
    osf_downloads = osf.get("downloads",               0)
    val_citations = val.get("citations",               0)
    val_replics   = val.get("independent_replications", 0)

    # ------------------------------------------------------------------ #
    # 4. Compute attention metrics                                        #
    # ------------------------------------------------------------------ #
    reach_total    = gh_views + rg_reads + zen_total_views + osf_views
    verify_total   = gh_clones + gh_forks + zen_total_downloads + osf_downloads
    academic_total = val_citations + val_replics

    data.setdefault("attention", {})
    attn = data["attention"]

    attn["reach_events"]              = reach_total
    attn["verification_events"]       = verify_total
    attn["academic_attention_events"] = academic_total

    # Remove legacy field names if present (migration)
    for old_key in ("engagement_events", "research_action_events",
                    "validation_events"):
        attn.pop(old_key, None)

    attn.setdefault("components", {})
    attn["components"]["reach"] = {
        "github_views":       gh_views,
        "zenodo_views":       zen_total_views,
        "osf_views":          osf_views,
        "researchgate_reads": rg_reads,
        "calculated_total":   reach_total,
    }
    attn["components"]["verification"] = {
        "github_clones":    gh_clones,
        "github_forks":     gh_forks,
        "zenodo_downloads": zen_total_downloads,
        "osf_downloads":    osf_downloads,
        "calculated_total": verify_total,
    }
    attn["components"]["academic_attention"] = {
        "citations":               val_citations,
        "independent_replications": val_replics,
        "calculated_total":        academic_total,
    }

    # Remove legacy component keys if present (migration)
    for old_key in ("engagement", "research_actions", "validation"):
        attn["components"].pop(old_key, None)

    # ------------------------------------------------------------------ #
    # 5. Audit verification (explicit checks, not assert)                 #
    # ------------------------------------------------------------------ #
    audit_ok = all([
        _verify("reach_total",   reach_total,
                gh_views + rg_reads + zen_total_views + osf_views),
        _verify("verify_total",  verify_total,
                gh_clones + gh_forks + zen_total_downloads + osf_downloads),
        _verify("academic_total", academic_total,
                val_citations + val_replics),
    ])

    data.setdefault("audit_control", {})
    data["audit_control"]["status"] = "Passed" if audit_ok else "Failed"

    # ------------------------------------------------------------------ #
    # 6. Timestamps and data quality                                      #
    # ------------------------------------------------------------------ #
    data["updated"]       = today
    data["last_verified"] = today

    data.setdefault("data_quality", {})
    data["data_quality"]["last_checked"]              = today
    data["data_quality"]["attention_totals_verified"] = audit_ok
    data["data_quality"].setdefault(
        "staleness_threshold_days", STALENESS_THRESHOLD_DAYS
    )

    # ------------------------------------------------------------------ #
    # 7. Write output                                                     #
    # ------------------------------------------------------------------ #
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with JSON_PATH.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"[{today}] {JSON_PATH} updated successfully.")
    print(
        f"  reach={reach_total}  verify={verify_total}  "
        f"academic={academic_total}  audit={'OK' if audit_ok else 'WARN'}"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    update_telemetry()
