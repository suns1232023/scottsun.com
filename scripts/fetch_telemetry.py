#!/usr/bin/env python3
"""
fetch_telemetry.py — Scholarly Metrics & Attention Telemetry Engine
---------------------------------------------------------------------
Author: Scott Sun
Description: Fetches live statistics from Zenodo API and merges metrics into 
             data/attention.json (Schema v3.0) without losing GitHub/RG totals.
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

# 双路径自动容错：优先查找 scholarly/publications.json，回退至 data/publications.json
PRIMARY_PUB_PATH = os.path.join(ROOT_DIR, "scholarly", "publications.json")
FALLBACK_PUB_PATH = os.path.join(ROOT_DIR, "data", "publications.json")

ATTENTION_JSON = os.path.join(ROOT_DIR, "data", "attention.json")
ZENODO_API_URL = "https://zenodo.org/api/records/"


def get_publications_file_path() -> str:
    """Returns the existing publications.json file path."""
    if os.path.exists(PRIMARY_PUB_PATH):
        return PRIMARY_PUB_PATH
    elif os.path.exists(FALLBACK_PUB_PATH):
        return FALLBACK_PUB_PATH
    else:
        logger.error(f"Missing publications metadata in both {PRIMARY_PUB_PATH} and {FALLBACK_PUB_PATH}")
        raise FileNotFoundError("publications.json not found in scholarly/ or data/")


def load_publications() -> Dict[str, Any]:
    file_path = get_publications_file_path()
    logger.info(f"Loading publication metadata from: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
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

    # 读取现有 attention.json 以保留结构和历史数据，如果不存在则使用默认基底
    if os.path.exists(ATTENTION_JSON):
        with open(ATTENTION_JSON, "r", encoding="utf-8") as f:
            attention_data = json.load(f)
    else:
        attention_data = {
            "_schema_version": "3.0",
            "github": {"totals": {"views": 0, "unique_visitors": 0, "clones": 0, "forks": 0, "stars": 0}},
            "zenodo": {"totals": {"total_views": 0, "unique_views": 0, "total_downloads": 0, "unique_downloads": 0}},
            "researchgate": {"total_reads": 0, "total_recommendations": 0},
            "google_scholar": {"citations_total": 0},
            "attention": {"reach_events": 0, "engagement_events": 0, "research_action_events": 0, "academic_attention_events": 0}
        }

    # 更新元数据与时间戳
    attention_data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    attention_data["last_verified"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    total_zenodo_views = 0
    total_zenodo_downloads = 0
    pub_records = []

    for pub in publications:
        pub_id = pub.get("id")
        doi = pub.get("doi", "")
        record_id = extract_zenodo_id(doi)

        zenodo_stats = fetch_zenodo_metrics(record_id) if record_id else {"views": 0, "downloads": 0, "status": "no_record_id"}

        if zenodo_stats.get("status") == "success":
            total_zenodo_views += zenodo_stats["views"]
            total_zenodo_downloads += zenodo_stats["downloads"]

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
        pub_records.append(record_entry)

    # 保持 zenodo totals 汇总更新
    if "zenodo" not in attention_data:
        attention_data["zenodo"] = {"totals": {}}
    attention_data["zenodo"]["totals"]["total_views"] = max(total_zenodo_views, attention_data["zenodo"]["totals"].get("total_views", 0))
    attention_data["zenodo"]["totals"]["total_downloads"] = max(total_zenodo_downloads, attention_data["zenodo"]["totals"].get("total_downloads", 0))

    attention_data["publications"] = pub_records

    os.makedirs(os.path.dirname(ATTENTION_JSON), exist_ok=True)
    with open(ATTENTION_JSON, "w", encoding="utf-8") as f:
        json.dump(attention_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Successfully merged & updated {ATTENTION_JSON} (Schema v3.0)!")


if __name__ == "__main__":
    main()
