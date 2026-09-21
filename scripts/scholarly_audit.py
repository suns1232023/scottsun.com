from datetime import date
import json
import re
import sys
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]

METADATA = ROOT / "scholarly" / "publications.json"
CITATION = ROOT / "CITATION.cff"
REPORT_DIR = ROOT / "reports"

REPORT_DIR.mkdir(exist_ok=True)


def normalize(text):
    """
    Normalize strings for title comparison.
    Remove punctuation, spaces and case differences.
    """
    if not text:
        return ""

    text_clean = " ".join(str(text).split())

    return re.sub(
        r"[^a-z0-9]+",
        "",
        text_clean.lower()
    )


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_author_names(pub):
    """
    Supports both:

    author: "Scott Sun"

    and

    authors:
      - {name: Scott Sun}
      - {name: Solomon Chen}
    """

    authors_data = pub.get("authors")

    if isinstance(authors_data, list):

        names = []

        for author in authors_data:

            if isinstance(author, dict):
                names.append(author.get("name", ""))

            elif isinstance(author, str):
                names.append(author)

        return " ".join(names)

    return pub.get("author", "")


def crossref_lookup(doi):

    url = f"https://api.crossref.org/works/{doi}"

    headers = {
        "User-Agent":
            "ScholarlyAudit/1.0 "
            "(https://github.com; "
            "mailto:contact@scottsun.com)"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if response.status_code == 404:
            print(
                f"[WARN] Crossref record not found: {doi}"
            )
            return None

        response.raise_for_status()

        return response.json().get(
            "message",
            {}
        )

    except Exception as e:

        print(
            f"[WARN] Crossref lookup failed for {doi}: {e}"
        )

        return None


def openalex_lookup(doi):

    clean_doi = (
        doi.replace(
            "https://doi.org/",
            ""
        )
        .strip()
    )

    url = (
        "https://api.openalex.org/works/"
        f"https://doi.org/{clean_doi}"
    )

    headers = {
        "User-Agent":
            "ScholarlyAudit/1.0 "
            "(mailto:contact@scottsun.com)"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if response.status_code == 404:

            print(
                f"[WARN] OpenAlex record not found: {clean_doi}"
            )

            return None

        response.raise_for_status()

        return response.json()

    except Exception as e:

        print(
            f"[WARN] OpenAlex lookup failed for "
            f"{clean_doi}: {e}"
        )

        return None


def audit_citation_cff():

    if not CITATION.exists():

        print(
            "[WARN] CITATION.cff is missing"
        )

        return False, [
            "CITATION.cff missing"
        ]

    try:

        with open(
            CITATION,
            "r",
            encoding="utf-8"
        ) as f:

            data = yaml.safe_load(f)

        if not isinstance(data, dict):

            return False, [
                "CITATION.cff format invalid"
            ]

        print(
            "[PASS] CITATION.cff validated"
        )

        return True, []

    except Exception as e:

        print(
            f"[ERROR] Failed to parse "
            f"CITATION.cff: {e}"
        )

        return False, [
            f"CITATION.cff parse error: {e}"
        ]


def audit_publication(pub):

    errors = []
    warnings = []

    title = pub.get("title")
    doi = pub.get("doi")

    author_str = extract_author_names(pub)

    print("\n----------------------------------------")
    print(f"Title: {title or 'UNKNOWN'}")
    print("----------------------------------------")

    if not title:
        errors.append("Missing title")

    if not doi:
        errors.append("Missing DOI")

    if doi and not str(doi).startswith("10."):
        warnings.append(
            "DOI format appears unusual"
        )

    if not author_str:
        warnings.append(
            "Missing author"
        )

    # --------------------
    # Crossref
    # --------------------

    crossref = None

    if doi:
        crossref = crossref_lookup(doi)

    if crossref:

        cr_titles = crossref.get(
            "title",
            []
        )

        cr_title = (
            cr_titles[0]
            if cr_titles
            else ""
        )

        print(
            f"[INFO] Crossref title: {cr_title}"
        )

        if (
            title
            and cr_title
            and normalize(title)
            != normalize(cr_title)
        ):
            warnings.append(
                "Title mismatch with Crossref"
            )

        cr_authors = crossref.get(
            "author",
            []
        )

        if cr_authors:

            family_name = (
                cr_authors[0]
                .get("family", "")
            )

            if (
                author_str
                and family_name
                and normalize(family_name)
                not in normalize(author_str)
            ):
                warnings.append(
                    "Author mismatch with Crossref"
                )

    else:

        warnings.append(
            "Publication record pending or not in Crossref"
        )

    # --------------------
    # OpenAlex
    # --------------------

    openalex = None

    if doi:
        openalex = openalex_lookup(doi)

    if openalex:

        print(
            "[PASS] OpenAlex record found"
        )

        oa_title = openalex.get(
            "display_name",
            ""
        )

        if (
            title
            and oa_title
            and normalize(title)
            != normalize(oa_title)
        ):
            warnings.append(
                "Title mismatch with OpenAlex"
            )

        citations = openalex.get(
            "cited_by_count",
            0
        )

        print(
            f"[INFO] OpenAlex citations: "
            f"{citations}"
        )

    else:

        warnings.append(
            "Publication not yet indexed in OpenAlex"
        )

    return errors, warnings


def main():

    print("\n========================================")
    print(" SCHOLARLY METADATA AUDIT")
    print("========================================")

    if not METADATA.exists():

        print(
            f"[ERROR] Missing file: {METADATA}"
        )

        sys.exit(1)

    cff_ok, cff_errors = audit_citation_cff()

    metadata = load_json(METADATA)

    publications = metadata.get(
        "publications",
        []
    )

    if not isinstance(publications, list):

        print(
            "[ERROR] publications must be a list"
        )

        sys.exit(1)

    total_errors = len(cff_errors)
    total_warnings = 0

    report = []

    for pub in publications:

        errors, warnings = audit_publication(pub)

        total_errors += len(errors)
        total_warnings += len(warnings)

        report.append({
            "id": pub.get("id"),
            "title": pub.get("title"),
            "doi": pub.get("doi"),
            "errors": errors,
            "warnings": warnings
        })

    result = {

        "schema_version": "1.1",

        "generated":
            date.today().isoformat(),

        "citation_cff_valid":
            cff_ok,

        "publications_count":
            len(publications),

        "total_errors":
            total_errors,

        "total_warnings":
            total_warnings,

        "results":
            report
    }

    output = REPORT_DIR / "scholarly-audit.json"

    with open(
        output,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    print("\n========================================")
    print(" SUMMARY")
    print("========================================")

    print(
        f"CITATION.cff Status: "
        f"{'PASS' if cff_ok else 'WARN/FAIL'}"
    )

    print(
        f"Publications Audited: "
        f"{len(publications)}"
    )

    print(
        f"Total Errors: "
        f"{total_errors}"
    )

    print(
        f"Total Warnings: "
        f"{total_warnings}"
    )

    print(
        f"Report Generated: "
        f"{output}"
    )

    if total_errors > 0:

        print("\nAUDIT STATUS: FAIL")

        sys.exit(1)

    print("\nAUDIT STATUS: PASS")


if __name__ == "__main__":
    main()
