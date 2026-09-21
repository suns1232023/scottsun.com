"""
scholarly_audit.py — Scott Sun Academic Homepage
Audits publications.json against Crossref and OpenAlex APIs,
validates CITATION.cff, and writes a JSON report.

Usage:
    python scripts/scholarly_audit.py

Output:
    reports/scholarly-audit.json
"""

from datetime import date
import json
import re
import sys
from pathlib import Path

import requests
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

METADATA    = ROOT / "scholarly" / "publications.json"
CITATION    = ROOT / "CITATION.cff"
REPORT_DIR  = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "scholarly-audit.json"

# Report schema version (output file)
REPORT_SCHEMA_VERSION = "1.1"

# HTTP timeouts (seconds)
HTTP_TIMEOUT = 20

# User-Agent sent to external APIs
USER_AGENT_CROSSREF = (
    "ScholarlyAudit/1.0 "
    "(https://github.com/scottsun; "
    "mailto:contact@scottsun.com)"
)
USER_AGENT_OPENALEX = (
    "ScholarlyAudit/1.0 "
    "(mailto:contact@scottsun.com)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_doi_string(raw_doi: str) -> str:
    """Strip protocol prefixes from DOIs to ensure uniform format (e.g. 10.5281/...)."""
    if not raw_doi:
        return ""
    doi = str(raw_doi).strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip()


def normalize(text: str) -> str:
    """
    Normalise a string for fuzzy title / author comparison.
    Strips punctuation, collapses whitespace, lowercases.
    """
    if not text:
        return ""
    collapsed = " ".join(str(text).split())
    return re.sub(r"[^a-z0-9]+", "", collapsed.lower())


def load_json(path: Path) -> dict:
    """Load and parse a JSON file; exit on error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Invalid JSON in {path}: {exc}")
        sys.exit(1)


def extract_author_names(pub: dict) -> str:
    """
    Return a single string of all author names, supporting both:
      - Legacy:  "author": "Scott Sun"
      - Current: "authors": [{"name": "Scott Sun"}, ...]
    """
    authors_data = pub.get("authors")

    if isinstance(authors_data, list):
        names = []
        for author in authors_data:
            if isinstance(author, dict):
                names.append(author.get("name", ""))
            elif isinstance(author, str):
                names.append(author)
        return " ".join(filter(None, names))

    # Fallback to legacy scalar field
    return pub.get("author", "")


# ---------------------------------------------------------------------------
# External API lookups
# ---------------------------------------------------------------------------

def crossref_lookup(raw_doi: str) -> dict | None:
    """
    Query Crossref Works API for a DOI.
    Returns the 'message' dict on success, None on failure.
    """
    doi = clean_doi_string(raw_doi)
    if not doi:
        return None

    url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": USER_AGENT_CROSSREF}

    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)

        if resp.status_code == 404:
            print(f"[WARN] Crossref: no record for DOI {doi}")
            return None

        resp.raise_for_status()
        return resp.json().get("message", {})

    except requests.RequestException as exc:
        print(f"[WARN] Crossref lookup failed for {doi}: {exc}")
        return None


def openalex_lookup(raw_doi: str) -> dict | None:
    """
    Query OpenAlex Works API for a DOI.
    Returns the work dict on success, None on failure.
    """
    doi = clean_doi_string(raw_doi)
    if not doi:
        return None

    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {"User-Agent": USER_AGENT_OPENALEX}

    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)

        if resp.status_code == 404:
            print(f"[WARN] OpenAlex: no record for DOI {doi}")
            return None

        resp.raise_for_status()
        return resp.json()

    except requests.RequestException as exc:
        print(f"[WARN] OpenAlex lookup failed for {doi}: {exc}")
        return None


# ---------------------------------------------------------------------------
# CITATION.cff audit
# ---------------------------------------------------------------------------

def audit_citation_cff() -> tuple[bool, list[str]]:
    """
    Validate that CITATION.cff exists and is parseable YAML.
    Returns (ok: bool, errors: list[str]).
    """
    if not CITATION.exists():
        print("[WARN] CITATION.cff is missing at repository root")
        return False, ["CITATION.cff missing"]

    try:
        with open(CITATION, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if not isinstance(data, dict):
            return False, ["CITATION.cff format invalid (not a mapping)"]

        # Basic required fields
        missing = [f for f in ("cff-version", "title", "authors") if f not in data]
        if missing:
            return False, [f"CITATION.cff missing fields: {missing}"]

        print("[PASS] CITATION.cff loaded and validated")
        return True, []

    except yaml.YAMLError as exc:
        print(f"[ERROR] Failed to parse CITATION.cff: {exc}")
        return False, [f"CITATION.cff parse error: {exc}"]


# ---------------------------------------------------------------------------
# Per-publication audit
# ---------------------------------------------------------------------------

def audit_publication(pub: dict) -> tuple[list[str], list[str]]:
    """
    Audit a single publication entry.
    Returns (errors, warnings).
    """
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

    # --- Required field checks ---
    if not title:
        errors.append("Missing title")

    if not doi:
        errors.append("Missing DOI")
    elif not doi.startswith("10."):
        warnings.append(f"DOI format appears unusual: {doi}")

    if not author_str:
        warnings.append("Missing author information")

    # --- peer_reviewed field ---
    if "peer_reviewed" not in pub:
        warnings.append("Missing 'peer_reviewed' field")
    elif pub["peer_reviewed"] is not False:
        # All current publications are preprints
        warnings.append(
            f"peer_reviewed={pub['peer_reviewed']!r} — "
            "verify this is intentional for a preprint"
        )

    # --- evidence_level field ---
    valid_evidence_levels = {
        "mathematical-proof",
        "computational-audit",
        "computational-candidate",
        "exploratory",
        "published",
        "research-program"
    }
    ev = pub.get("evidence_level", "")
    if not ev:
        warnings.append("Missing 'evidence_level' field")
    elif ev not in valid_evidence_levels:
        warnings.append(f"Unknown evidence_level: '{ev}'")

    # --- Crossref ---
    crossref = crossref_lookup(doi) if doi else None

    if crossref:
        cr_titles = crossref.get("title", [])
        cr_title  = cr_titles[0] if cr_titles else ""
        print(f"[INFO] Crossref title: {cr_title}")

        if title and cr_title and normalize(title) != normalize(cr_title):
            warnings.append("Title mismatch with Crossref")

        cr_authors = crossref.get("author", [])
        if cr_authors:
            family = cr_authors[0].get("family", "")
            if author_str and family and normalize(family) not in normalize(author_str):
                warnings.append("Author mismatch with Crossref")
    else:
        warnings.append("Publication record pending or not yet in Crossref")

    # --- OpenAlex ---
    openalex = openalex_lookup(doi) if doi else None

    if openalex:
        print("[PASS] OpenAlex record found")
        oa_title   = openalex.get("display_name", "")
        citations  = openalex.get("cited_by_count", 0)
        print(f"[INFO] OpenAlex citations: {citations}")

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

    # Ensure report directory exists
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Validate metadata file exists
    if not METADATA.exists():
        print(f"[ERROR] Missing required file: {METADATA}")
        sys.exit(1)

    # Validate CITATION.cff
    cff_ok, cff_errors = audit_citation_cff()

    # Load publications
    metadata     = load_json(METADATA)
    publications = metadata.get("publications", [])

    if not isinstance(publications, list):
        print("[ERROR] 'publications' must be a JSON array")
        sys.exit(1)

    # Cross-check declared count vs actual count
    declared_count = metadata.get("metadata", {}).get("publication_count")
    actual_count   = len(publications)
    if declared_count is not None and declared_count != actual_count:
        print(
            f"[WARN] metadata.publication_count={declared_count} "
            f"does not match actual count={actual_count}"
        )

    # Audit each publication
    total_errors   = len(cff_errors)
    total_warnings = 0
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

    # Build report
    result = {
        "_schema_version":    REPORT_SCHEMA_VERSION,
        "generated":          date.today().isoformat(),
        "citation_cff_valid": cff_ok,
        "publications_count": actual_count,
        "total_errors":       total_errors,
        "total_warnings":     total_warnings,
        "results":            report_entries,
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"CITATION.cff Status  : {'PASS' if cff_ok else 'WARN/FAIL'}")
    print(f"Publications Audited : {actual_count}")
    print(f"Total Errors         : {total_errors}")
    print(f"Total Warnings       : {total_warnings}")
    print(f"Report Written       : {REPORT_FILE}")

    if total_errors > 0:
        print("\nAUDIT STATUS: FAIL")
        sys.exit(1)

    print("\nAUDIT STATUS: PASS")


if __name__ == "__main__":
    main()
