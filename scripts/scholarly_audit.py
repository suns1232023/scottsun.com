#!/usr/bin/env python3
"""
scholarly_audit.py — Academic Homepage Metadata Audit
Audits publications.json against Crossref and OpenAlex APIs,
validates CITATION.cff, and writes a JSON report to reports/scholarly-audit.json.
"""

from datetime import date
import json
import re
import sys
from pathlib import Path

import requests

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML is not installed. Please install it via 'pip install pyyaml'")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

PRIMARY_METADATA = ROOT / "scholarly" / "publications.json"
FALLBACK_METADATA = ROOT / "data" / "publications.json"

if PRIMARY_METADATA.exists():
    METADATA = PRIMARY_METADATA
elif FALLBACK_METADATA.exists():
    METADATA = FALLBACK_METADATA
else:
    METADATA = PRIMARY_METADATA

CITATION    = ROOT / "CITATION.cff"
REPORT_DIR  = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "scholarly-audit.json"

REPORT_SCHEMA_VERSION = "1.1"
HTTP_TIMEOUT = 10

USER_AGENT_CROSSREF = (
    "ScholarlyAudit/1.0 "
    "(https://github.com/suns1232023; "
    "mailto:suns1232023@hotmail.com)"
)
USER_AGENT_OPENALEX = (
    "ScholarlyAudit/1.0 "
    "(mailto:suns1232023@hotmail.com)"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_doi_string(raw_doi: str) -> str:
    if not raw_doi:
        return ""
    doi = str(raw_doi).strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip().strip("/")


def normalize(text: str) -> str:
    if not text:
        return ""
    collapsed = " ".join(str(text).split())
    return re.sub(r"[^a-z0-9]+", "", collapsed.lower())


def load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        print(f"[ERROR] Invalid or unreadable JSON in {path}: {exc}")
        sys.exit(1)


def extract_author_names(pub: dict) -> str:
    authors_data = pub.get("authors")
    if isinstance(authors_data, list):
        names = []
        for author in authors_data:
            if isinstance(author, dict):
                names.append(author.get("name", ""))
            elif isinstance(author, str):
                names.append(author)
        return " ".join(filter(None, names))
    return str(pub.get("author", ""))


# ---------------------------------------------------------------------------
# External API lookups
# ---------------------------------------------------------------------------

def crossref_lookup(raw_doi: str) -> dict | None:
    doi = clean_doi_string(raw_doi)
    if not doi:
        return None
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": USER_AGENT_CROSSREF}
    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("message", {})
        else:
            print(f"[WARN] Crossref returned status {resp.status_code} for DOI {doi}")
            return None
    except Exception as exc:
        print(f"[WARN] Crossref lookup non-fatal exception for {doi}: {exc}")
        return None


def openalex_lookup(raw_doi: str) -> dict | None:
    doi = clean_doi_string(raw_doi)
    if not doi:
        return None
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {"User-Agent": USER_AGENT_OPENALEX}
    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[WARN] OpenAlex returned status {resp.status_code} for DOI {doi}")
            return None
    except Exception as exc:
        print(f"[WARN] OpenAlex lookup non-fatal exception for {doi}: {exc}")
        return None


# ---------------------------------------------------------------------------
# CITATION.cff audit
# ---------------------------------------------------------------------------

def audit_citation_cff() -> tuple[bool, list[str]]:
    if not CITATION.exists():
        print("[WARN] CITATION.cff is missing at repository root (Non-fatal)")
        return False, ["CITATION.cff missing"]

    try:
        with open(CITATION, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            return False, ["CITATION.cff format invalid"]

        missing = [f for f in ("cff-version", "title", "authors") if f not in data]
        if missing:
            return False, [f"CITATION.cff missing fields: {missing}"]

        print("[PASS] CITATION.cff loaded and validated")
        return True, []

    except Exception as exc:
        print(f"[WARN] Failed to parse CITATION.cff: {exc}")
        return False, [f"CITATION.cff parse warning: {exc}"]


# ---------------------------------------------------------------------------
# Per-publication audit
# ---------------------------------------------------------------------------

def audit_publication(pub: dict) -> tuple[list[str], list[str]]:
    errors:   list[str] = []
    warnings: list[str] = []

    title      = pub.get("title", "")
    raw_doi    = pub.get("doi", "")
    doi        = clean_doi_string(raw_doi)
    author_str = extract_author_names(pub)

    print("\n" + "─" * 60)
    print(f"Title : {title or 'UNKNOWN'}")
    print(f"DOI   : {doi   or 'MISSING'}")
    print("─" * 60)

    if not title:
        errors.append("Missing title")
    if not doi:
        errors.append("Missing DOI")

    if not author_str:
        warnings.append("Missing author information")

    valid_evidence_levels = {
        "mathematical-proof",
        "computational-audit",
        "computational-candidate",
        "exploratory",
        "published",
        "research-program",
        "theoretical-framework"
    }
    ev = pub.get("evidence_level", "")
    if ev and ev not in valid_evidence_levels:
        warnings.append(f"Non-standard evidence_level: '{ev}'")

    crossref = crossref_lookup(doi) if doi else None
    if crossref:
        cr_titles = crossref.get("title", [])
        cr_title  = cr_titles[0] if cr_titles else ""
        if title and cr_title and normalize(title) != normalize(cr_title):
            warnings.append("Title mismatch with Crossref")
    else:
        warnings.append("Publication pending or not indexed in Crossref")

    openalex = openalex_lookup(doi) if doi else None
    if openalex:
        oa_title = openalex.get("display_name", "")
        if title and oa_title and normalize(title) != normalize(oa_title):
            warnings.append("Title mismatch with OpenAlex")
    else:
        warnings.append("Publication not yet indexed in OpenAlex")

    return errors, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 60)
    print("  SCHOLARLY METADATA AUDIT")
    print("=" * 60)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    if not METADATA.exists():
        print(f"[ERROR] Missing metadata file: {METADATA}")
        sys.exit(1)

    print(f"[INFO] Auditing publications file: {METADATA}")

    cff_ok, cff_warnings = audit_citation_cff()
    metadata     = load_json(METADATA)
    publications = metadata.get("publications", [])

    if not isinstance(publications, list):
        print("[ERROR] 'publications' must be a JSON array")
        sys.exit(1)

    total_errors   = 0
    total_warnings = len(cff_warnings)
    report_entries = []

    for pub in publications:
        errors, warnings = audit_publication(pub)
        total_errors   += len(errors)
        total_warnings += len(warnings)
        report_entries.append({
            "id":       pub.get("id"),
            "title":    pub.get("title"),
            "doi":      pub.get("doi"),
            "errors":   errors,
            "warnings": warnings,
        })

    result = {
        "_schema_version":    REPORT_SCHEMA_VERSION,
        "generated":          date.today().isoformat(),
        "citation_cff_valid": cff_ok,
        "publications_count": len(publications),
        "total_errors":       total_errors,
        "total_warnings":     total_warnings,
        "results":            report_entries,
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"CITATION.cff Status  : {'PASS' if cff_ok else 'WARN'}")
    print(f"Publications Audited : {len(publications)}")
    print(f"Total Errors         : {total_errors}")
    print(f"Total Warnings       : {total_warnings}")
    print(f"Report Written       : {REPORT_FILE}")

    if total_errors > 0:
        print("\nAUDIT STATUS: FAIL (Missing essential metadata)")
        sys.exit(1)

    print("\nAUDIT STATUS: PASS")


if __name__ == "__main__":
    main()
