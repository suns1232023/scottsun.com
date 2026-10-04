
#!/usr/bin/env python3
"""
scholarly_audit.py — Academic Homepage Metadata Audit
Audits publications.json against DataCite/Crossref and OpenAlex APIs,
validates CITATION.cff, and writes a JSON report to reports/scholarly-audit.json.

V1.1 FIXES:
  1. null DOI with doi_note → WARNING (not ERROR): papers without a Zenodo
     deposit are legitimate; the doi_note field documents the reason.
  2. DOI routing: 10.5281/* (Zenodo/DataCite) → DataCite API instead of
     Crossref. Crossref does not index DataCite DOIs, so querying it always
     returns 404 for Zenodo preprints.
  3. OpenAlex 404 for new preprints → downgraded from WARNING to INFO:
     newly deposited preprints may not yet be indexed by OpenAlex.
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

PRIMARY_METADATA  = ROOT / "scholarly" / "publications.json"
FALLBACK_METADATA = ROOT / "data"      / "publications.json"

if PRIMARY_METADATA.exists():
    METADATA = PRIMARY_METADATA
elif FALLBACK_METADATA.exists():
    METADATA = FALLBACK_METADATA
else:
    METADATA = PRIMARY_METADATA

CITATION    = ROOT / "CITATION.cff"
REPORT_DIR  = ROOT / "reports"
REPORT_FILE = REPORT_DIR / "scholarly-audit.json"

REPORT_SCHEMA_VERSION = "1.2"
HTTP_TIMEOUT = 12

USER_AGENT_CROSSREF  = (
    "ScholarlyAudit/1.1 "
    "(https://github.com/suns1232023; "
    "mailto:suns1232023@hotmail.com)"
)
USER_AGENT_DATACITE  = (
    "ScholarlyAudit/1.1 "
    "(https://github.com/suns1232023; "
    "mailto:suns1232023@hotmail.com)"
)
USER_AGENT_OPENALEX  = (
    "ScholarlyAudit/1.1 "
    "(mailto:suns1232023@hotmail.com)"
)

# DOI prefixes that belong to DataCite (not Crossref)
DATACITE_PREFIXES = ("10.5281",)   # Zenodo; extend as needed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean_doi_string(raw_doi) -> str:
    if not raw_doi:
        return ""
    doi = str(raw_doi).strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    return doi.strip().strip("/")


def is_datacite_doi(doi: str) -> bool:
    """Return True if this DOI prefix is managed by DataCite (e.g. Zenodo)."""
    return any(doi.startswith(prefix) for prefix in DATACITE_PREFIXES)


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

def crossref_lookup(doi: str) -> dict | None:
    """Query Crossref API. Only appropriate for non-DataCite DOIs."""
    url = f"https://api.crossref.org/works/{doi}"
    headers = {"User-Agent": USER_AGENT_CROSSREF}
    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            return resp.json().get("message", {})
        print(f"[WARN] Crossref returned status {resp.status_code} for DOI {doi}")
        return None
    except Exception as exc:
        print(f"[WARN] Crossref lookup non-fatal exception for {doi}: {exc}")
        return None


def datacite_lookup(doi: str) -> dict | None:
    """
    Query DataCite API for DOIs with prefix 10.5281 (Zenodo) and other
    DataCite-managed prefixes.

    DataCite REST API: https://api.datacite.org/dois/{doi}
    Returns the 'data.attributes' dict on success, None on failure.
    """
    url = f"https://api.datacite.org/dois/{doi}"
    headers = {"User-Agent": USER_AGENT_DATACITE}
    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            payload = resp.json()
            return payload.get("data", {}).get("attributes", {})
        print(f"[WARN] DataCite returned status {resp.status_code} for DOI {doi}")
        return None
    except Exception as exc:
        print(f"[WARN] DataCite lookup non-fatal exception for {doi}: {exc}")
        return None


def openalex_lookup(doi: str) -> dict | None:
    """Query OpenAlex API. Returns None without warning if not yet indexed."""
    url = f"https://api.openalex.org/works/https://doi.org/{doi}"
    headers = {"User-Agent": USER_AGENT_OPENALEX}
    try:
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        # 404 is normal for new preprints — log as INFO, not WARN
        if resp.status_code == 404:
            print(f"[INFO] OpenAlex: DOI {doi} not yet indexed (normal for new preprints)")
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
    raw_doi    = pub.get("doi")          # may be None/null
    doi_note   = pub.get("doi_note", "") # explanation when doi is null
    doi        = clean_doi_string(raw_doi)
    author_str = extract_author_names(pub)

    print("\n" + "─" * 60)
    print(f"Title : {title or 'UNKNOWN'}")
    print(f"DOI   : {doi   or 'MISSING'}")
    if doi_note and not doi:
        print(f"Note  : {doi_note}")
    print("─" * 60)

    # ── Required field checks ──────────────────────────────────────────────
    if not title:
        errors.append("Missing title")

    if not doi:
        # FIX: null DOI with doi_note → WARNING (not ERROR)
        # A paper without a Zenodo deposit is legitimate; doi_note documents why.
        if doi_note:
            warnings.append(f"No DOI (documented): {doi_note}")
            print(f"[INFO] No DOI — documented in doi_note field (not an error)")
        else:
            errors.append("Missing DOI — add a DOI or add a doi_note explaining its absence")
            print(f"[ERROR] Missing DOI with no doi_note explanation")

    if not author_str:
        warnings.append("Missing author information")

    # ── Evidence level check ───────────────────────────────────────────────
    valid_evidence_levels = {
        "mathematical-proof",
        "computational-audit",
        "computational-candidate",
        "exploratory",
        "published",
        "research-program",
        "theoretical-framework",
    }
    ev = pub.get("evidence_level", "")
    if ev and ev not in valid_evidence_levels:
        warnings.append(f"Non-standard evidence_level: '{ev}'")

    # ── DOI verification via correct API ──────────────────────────────────
    if doi:
        if is_datacite_doi(doi):
            # FIX: Use DataCite API for 10.5281/* (Zenodo) DOIs
            print(f"[INFO] Routing {doi} to DataCite API (Zenodo/DataCite prefix)")
            datacite = datacite_lookup(doi)
            if datacite:
                # Verify title against DataCite metadata
                dc_titles = datacite.get("titles", [])
                dc_title  = dc_titles[0].get("title", "") if dc_titles else ""
                if title and dc_title and normalize(title) != normalize(dc_title):
                    warnings.append(f"Title mismatch with DataCite: '{dc_title[:80]}'")
                else:
                    print(f"[PASS] DataCite record found and title matches")
            else:
                warnings.append("DOI not found in DataCite — verify the Zenodo record exists")
        else:
            # Non-DataCite DOI → use Crossref
            crossref = crossref_lookup(doi)
            if crossref:
                cr_titles = crossref.get("title", [])
                cr_title  = cr_titles[0] if cr_titles else ""
                if title and cr_title and normalize(title) != normalize(cr_title):
                    warnings.append("Title mismatch with Crossref")
                else:
                    print(f"[PASS] Crossref record found")
            else:
                warnings.append("Publication pending or not indexed in Crossref")

        # OpenAlex lookup (informational — 404 is not a warning for new preprints)
        openalex = openalex_lookup(doi)
        if openalex:
            oa_title = openalex.get("display_name", "")
            if title and oa_title and normalize(title) != normalize(oa_title):
                warnings.append("Title mismatch with OpenAlex")
            else:
                print(f"[PASS] OpenAlex record found")
        # No warning if OpenAlex returns 404 — already logged as INFO above

    return errors, warnings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 60)
    print("  SCHOLARLY METADATA AUDIT  (v1.2)")
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
