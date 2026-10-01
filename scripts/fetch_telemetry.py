#!/usr/bin/env python3
"""
fetch_telemetry.py — Scholarly Metrics & Attention Telemetry Engine
---------------------------------------------------------------------
Author: Scott Sun
Description:
    Fetches live Zenodo statistics for each publication listed in
    scholarly/publications.json and merges them into data/attention.json
    (Schema v3.0) without overwriting GitHub or ResearchGate totals.

    Key design rules:
    - Each unique Zenodo record ID is fetched exactly once, even if
      multiple publications share the same DOI.
    - Publications without a dedicated Zenodo DOI (doi: null) are
      skipped gracefully; their telemetry entry records status "no_doi".
    - Zenodo totals are updated monotonically (never decrease).
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import requests

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fetch_telemetry")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dual-path fallback: prefer scholarly/publications.json, fall back to data/
PRIMARY_PUB_PATH  = os.path.join(ROOT_DIR, "scholarly", "publications.json")
FALLBACK_PUB_PATH = os.path.join(ROOT_DIR, "data",      "publications.json")

ATTENTION_JSON = os.path.join(ROOT_DIR, "data", "attention.json")
ZENODO_API_URL = "https://zenodo.org/api/records/"


def get_publications_file_path() -> str:
    """Return the path to the existing publications.json file."""
    if os.path.exists(PRIMARY_PUB_PATH):
        return PRIMARY_PUB_PATH
    if os.path.exists(FALLBACK_PUB_PATH):
        return FALLBACK_PUB_PATH
    logger.error(
        f"Missing publications metadata in both "
        f"{PRIMARY_PUB_PATH} and {FALLBACK_PUB_PATH}"
    )
    raise FileNotFoundError("publications.json not found in scholarly/ or data/")


def load_publications() -> Dict[str, Any]:
    file_path = get_publications_file_path()
    logger.info(f"Loading publication metadata from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_zenodo_id(doi_or_url: str | None) -> Optional[str]:
    """Extract the numeric Zenodo record ID from a DOI or URL string.

    Returns None if the input is None, empty, or does not end with digits.
    """
    if not doi_or_url:
        return None
    # Works for both "10.5281/zenodo.12345678" and "https://zenodo.org/records/12345678"
    last = doi_or_url.rstrip("/").split("/")[-1]
    if last.isdigit():
        return last
    last = doi_or_url.rstrip("/").split(".")[-1]
    if last.isdigit():
        return last
    return None


def fetch_zenodo_metrics(record_id: str) -> Dict[str, Any]:
    """Fetch view and download statistics for a single Zenodo record.

    Returns a dict with keys: record_id, views, downloads, version, status.
    On HTTP or network error, views/downloads default to 0 and status
    records the failure reason.
    """
    url = f"{ZENODO_API_URL}{record_id}"
    metrics: Dict[str, Any] = {
        "record_id": record_id,
        "views":     0,
        "downloads": 0,
        "version":   None,
        "status":    "success",
    }
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data  = response.json()
            stats = data.get("stats", {})
            metrics["views"]     = stats.get("views",    0)
            metrics["downloads"] = stats.get("downloads", 0)
            metrics["version"]   = data.get("metadata", {}).get("version")
            logger.info(
                f"Zenodo {record_id}: "
                f"{metrics['views']} views, {metrics['downloads']} downloads"
            )
        else:
            metrics["status"] = f"error_http_{response.status_code}"
            logger.warning(
                f"Zenodo API returned HTTP {response.status_code} "
                f"for record {record_id}"
            )
    except Exception as exc:
        metrics["status"] = f"exception_{type(exc).__name__}"
        logger.warning(f"Network error fetching Zenodo record {record_id}: {exc}")
    return metrics


def main() -> None:
    logger.info("Initialising telemetry update for data/attention.json …")
    pubs_data    = load_publications()
    publications = pubs_data.get("publications", [])

    # Load existing attention.json to preserve GitHub / RG / GS totals
    if os.path.exists(ATTENTION_JSON):
        with open(ATTENTION_JSON, "r", encoding="utf-8") as f:
            attention_data = json.load(f)
    else:
        attention_data = {
            "_schema_version": "3.0",
            "github":    {"totals": {"views": 0, "unique_visitors": 0,
                                     "clones": 0, "forks": 0, "stars": 0}},
            "zenodo":    {"totals": {"total_views": 0, "unique_views": 0,
                                     "total_downloads": 0, "unique_downloads": 0}},
            "researchgate":  {"total_reads": 0, "total_recommendations": 0},
            "google_scholar": {"citations_total": 0},
            "attention": {"reach_events": 0, "engagement_events": 0,
                          "research_action_events": 0, "academic_attention_events": 0},
        }

    # Update timestamps
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attention_data["updated"]      = today
    attention_data["last_verified"] = today

    # ------------------------------------------------------------------
    # Fetch Zenodo stats — each unique record ID fetched exactly once
    # ------------------------------------------------------------------
    fetched_records: Dict[str, Dict[str, Any]] = {}   # record_id → metrics
    total_zenodo_views     = 0
    total_zenodo_downloads = 0
    pub_records            = []

    for pub in publications:
        pub_id    = pub.get("id")
        doi       = pub.get("doi")          # may be None for RG-only papers
        record_id = extract_zenodo_id(doi)

        if record_id is None:
            # No Zenodo deposit for this publication
            zenodo_stats = {
                "views": 0, "downloads": 0,
                "version": None, "status": "no_doi",
            }
            logger.info(
                f"Skipping Zenodo fetch for '{pub_id}' "
                f"(no dedicated Zenodo DOI)"
            )
        elif record_id in fetched_records:
            # Duplicate DOI — reuse cached result, do NOT add to totals again
            zenodo_stats = fetched_records[record_id]
            logger.info(
                f"Reusing cached Zenodo stats for '{pub_id}' "
                f"(record {record_id} already fetched)"
            )
        else:
            zenodo_stats = fetch_zenodo_metrics(record_id)
            fetched_records[record_id] = zenodo_stats
            if zenodo_stats.get("status") == "success":
                total_zenodo_views     += zenodo_stats["views"]
                total_zenodo_downloads += zenodo_stats["downloads"]

        pub_records.append({
            "id":             pub_id,
            "title":          pub.get("title"),
            "doi":            doi,
            "year":           pub.get("year"),
            "version":        pub.get("version"),
            "type":           pub.get("type"),
            "status":         pub.get("status"),
            "evidence_level": pub.get("evidence_level"),
            "telemetry": {
                "zenodo_views":     zenodo_stats.get("views",     0),
                "zenodo_downloads": zenodo_stats.get("downloads", 0),
                "status":           zenodo_stats.get("status"),
            },
            "links": pub.get("links", {}),
        })

    # Monotonic preservation for Zenodo totals
    attention_data.setdefault("zenodo", {}).setdefault("totals", {})
    existing_z = attention_data["zenodo"]["totals"]
    attention_data["zenodo"]["totals"]["total_views"] = max(
        total_zenodo_views,     existing_z.get("total_views",     0)
    )
    attention_data["zenodo"]["totals"]["total_downloads"] = max(
        total_zenodo_downloads, existing_z.get("total_downloads", 0)
    )

    attention_data["publications"] = pub_records

    os.makedirs(os.path.dirname(ATTENTION_JSON), exist_ok=True)
    with open(ATTENTION_JSON, "w", encoding="utf-8") as f:
        json.dump(attention_data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    logger.info(
        f"Successfully merged & updated {ATTENTION_JSON} (Schema v3.0) — "
        f"total Zenodo: {total_zenodo_views} views, "
        f"{total_zenodo_downloads} downloads across "
        f"{len(fetched_records)} unique records"
    )


if __name__ == "__main__":
    main()
