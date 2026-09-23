#!/usr/bin/env python3
"""
fetch_telemetry.py — Scholarly Metrics & Telemetry Harvester
------------------------------------------------------------
Author: Scott Sun
Description: Fetches real-time telemetry (Zenodo views/downloads, DOI metadata,
             and optional GitHub repository stats) based on scholarly/publications.json.
Output: reports/telemetry.json
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fetch_telemetry")

# File paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLICATIONS_JSON = os.path.join(ROOT_DIR, "scholarly", "publications.json")
OUTPUT_TELEMETRY_JSON = os.path.join(ROOT_DIR, "reports", "telemetry.json")

# Endpoint URLs
ZENODO_API_URL = "https://zenodo.org/api/records/"


def load_publications() -> Dict[str, Any]:
    """Loads publication metadata from scholarly/publications.json."""
    if not os.path.exists(PUBLICATIONS_JSON):
        logger.error(f"File not found: {PUBLICATIONS_JSON}")
        raise FileNotFoundError(f"Missing {PUBLICATIONS_JSON}")
    
    with open(PUBLICATIONS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_zenodo_id(doi_or_url: str) -> Optional[str]:
    """Extracts Zenodo record ID from DOI string or Zenodo URL."""
    if not doi_or_url:
        return None
    # Handles "10.5281/zenodo.22139197" or "https://zenodo.org/record/22139197"
    parts = doi_or_url.rstrip("/").split(".")
    if len(parts) > 0 and parts[-1].isdigit():
        return parts[-1]
    
    slash_parts = doi_or_url.rstrip("/").split("/")
    if len(slash_parts) > 0 and slash_parts[-1].isdigit():
        return slash_parts[-1]
    
    return None


def fetch_zenodo_metrics(record_id: str) -> Dict[str, Any]:
    """Fetches stats (views, downloads, version info) from Zenodo REST API."""
    url = f"{ZENODO_API_URL}{record_id}"
    metrics = {
        "record_id": record_id,
        "views": 0,
        "downloads": 0,
        "version": None,
        "created": None,
        "conceptrecid": None,
        "status": "success"
    }

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            metrics["views"] = stats.get("views", 0)
            metrics["downloads"] = stats.get("downloads", 0)
            metrics["version"] = data.get("metadata", {}).get("version")
            metrics["created"] = data.get("created")
            metrics["conceptrecid"] = data.get("conceptrecid")
            logger.info(f"Successfully fetched Zenodo Record {record_id}: {metrics['views']} views, {metrics['downloads']} downloads.")
        else:
            logger.warning(f"Failed to fetch Zenodo Record {record_id}: HTTP {response.status_code}")
            metrics["status"] = f"error_http_{response.status_code}"
    except Exception as e:
        logger.error(f"Exception while querying Zenodo API for record {record_id}: {str(e)}")
        metrics["status"] = f"exception_{type(e).__name__}"

    return metrics


def main():
    logger.info("Starting scholarly telemetry collection...")
    pubs_data = load_publications()
    publications = pubs_data.get("publications", [])

    telemetry_report = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_publications_audited": len(publications),
            "source_schema_version": pubs_data.get("_schema_version", "2.0")
        },
        "aggregate_stats": {
            "total_views": 0,
            "total_downloads": 0,
            "successful_queries": 0
        },
        "records": []
    }

    for pub in publications:
        pub_id = pub.get("id")
        doi = pub.get("doi", "")
        record_id = extract_zenodo_id(doi)

        record_telemetry = {
            "id": pub_id,
            "doi": doi,
            "zenodo_record_id": record_id,
            "title": pub.get("title"),
            "type": pub.get("type"),
            "evidence_level": pub.get("evidence_level"),
            "metrics": {}
        }

        if record_id:
            zenodo_stats = fetch_zenodo_metrics(record_id)
            record_telemetry["metrics"] = zenodo_stats

            if zenodo_stats["status"] == "success":
                telemetry_report["aggregate_stats"]["total_views"] += zenodo_stats["views"]
                telemetry_report["aggregate_stats"]["total_downloads"] += zenodo_stats["downloads"]
                telemetry_report["aggregate_stats"]["successful_queries"] += 1
        else:
            logger.warning(f"No valid Zenodo ID extracted for publication ID '{pub_id}' (DOI: '{doi}').")
            record_telemetry["metrics"]["status"] = "missing_record_id"

        telemetry_report["records"].append(record_telemetry)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_TELEMETRY_JSON), exist_ok=True)
    
    with open(OUTPUT_TELEMETRY_JSON, "w", encoding="utf-8") as f:
        json.dump(telemetry_report, f, indent=2, ensure_ascii=False)

    logger.info(f"Telemetry harvesting complete! Summary: {telemetry_report['aggregate_stats']}")
    logger.info(f"Report exported to: {OUTPUT_TELEMETRY_JSON}")


if __name__ == "__main__":
    main()
