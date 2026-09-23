#!/usr/bin/env python3
"""
fetch_telemetry.py — Scholarly Metrics & Attention Telemetry Engine
---------------------------------------------------------------------
Author: Scott Sun
Description: Reads data/publications.json, fetches live statistics from Zenodo API,
             and backwrites aggregated metrics to data/attention.json (Schema v3.0).
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
PUBLICATIONS_JSON = os.path.join(ROOT_DIR, "data", "publications.json")
ATTENTION_JSON = os.path.join(ROOT_DIR, "data", "attention.json")

ZENODO_API_URL = "https://zenodo.org/api/records/"


def load_publications() -> Dict[str, Any]:
    if not os.path.exists(PUBLICATIONS_JSON):
        logger.error(f"File not found: {PUBLICATIONS_JSON}")
        raise FileNotFoundError(f"Missing {PUBLICATIONS_JSON}")
    
    with open(PUBLICATIONS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_zenodo_id(doi_or_url: str) -> Optional[str]:
    if not doi_or_url:
        return None
    parts = doi_or_url.rstrip("/").split(".")
    if len(parts) > 0 and parts[-1].isdigit():
        return parts[-1]
    
    slash_parts = doi_or_url.rstrip("/").split("/")
    if len(slash_parts) > 0 and slash_parts[-1].isdigit():
        return slash_parts[-1]
    
    return None


def fetch_zenodo_metrics(record_id: str) -> Dict[str, Any]:
    url = f"{ZENODO_API_URL}{record_id}"
    metrics = {
        "record_id": record_id,
        "views": 0,
        "downloads": 0,
        "version": None,
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
            logger.info(f"Fetched Zenodo Record {record_id}: {metrics['views']} views, {metrics['downloads']} downloads.")
        else:
            metrics["status"] = f"error_http_{response.status_code}"
    except Exception as e:
        metrics["status"] = f"exception_{type(e).__name__}"

    return metrics


def main():
    logger.info("Initializing telemetry update for data/attention.json...")
    pubs_data = load_publications()
    publications = pubs_data.get("publications", [])

    attention_data = {
        "_comment": "Scott Sun — Scholarly Attention & Telemetry Store | data/attention.json",
        "_schema_version": "3.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "author": pubs_data.get("author", {"name": "Scott Sun", "orcid": "0009-0002-1095-6228"}),
        "summary": {
            "total_publications": len(publications),
            "total_views": 0,
            "total_downloads": 0
        },
        "publications": []
    }

    for pub in publications:
        pub_id = pub.get("id")
        doi = pub.get("doi", "")
        record_id = extract_zenodo_id(doi)

        zenodo_stats = fetch_zenodo_metrics(record_id) if record_id else {"views": 0, "downloads": 0, "status": "no_record_id"}

        if zenodo_stats.get("status") == "success":
            attention_data["summary"]["total_views"] += zenodo_stats["views"]
            attention_data["summary"]["total_downloads"] += zenodo_stats["downloads"]

        record_entry = {
            "id": pub_id,
            "title": pub.get("title"),
            "doi": doi,
            "year": pub.get("year"),
            "version": pub.get("version"),
            "type": pub.get("type"),
            "status": pub.get("status"),
            "evidence_level": pub.get("evidence_level"),
            "telemetry": {
                "zenodo_views": zenodo_stats.get("views", 0),
                "zenodo_downloads": zenodo_stats.get("downloads", 0),
                "status": zenodo_stats.get("status")
            },
            "links": pub.get("links", {})
        }
        attention_data["publications"].append(record_entry)

    os.makedirs(os.path.dirname(ATTENTION_JSON), exist_ok=True)
    with open(ATTENTION_JSON, "w", encoding="utf-8") as f:
        json.dump(attention_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully updated {ATTENTION_JSON} (Schema v3.0)!")


if __name__ == "__main__":
    main()
