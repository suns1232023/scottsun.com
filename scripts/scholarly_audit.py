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
    if not text:
        return ""

    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(text).lower()
    )


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_file(path, label):
    if path.exists():
        print(f"[PASS] {label}")
        return True

    print(f"[WARN] {label} missing")
    return False


def extract_author_names(pub):
    """
    兼顾旧版 'author': 'Scott Sun' 
    与新版 'authors': [{'name': 'Scott Sun'}, {'name': 'Solomon Chen'}] 结构
    """
    authors_data = pub.get("authors")
    if isinstance(authors_data, list):
        names = []
        for a in authors_data:
            if isinstance(a, dict):
                names.append(a.get("name", ""))
            elif isinstance(a, str):
                names.append(a)
        return " ".join(names)

    return pub.get("author", "")


def crossref_lookup(doi):
    url = f"https://api.crossref.org/works/{doi}"

    headers = {
        "User-Agent":
        "ScottSun-ScholarlyAudit/1.0 "
        "(metadata validation)"
    }

    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        r.raise_for_status()

        return r.json()["message"]

    except Exception as e:
        print(
            f"[ERROR] Crossref lookup failed for "
            f"{doi}: {e}"
        )

        return None


def openalex_lookup(doi):
    url = (
        "https://api.openalex.org/works/"
        f"https://doi.org/{doi}"
    )

    try:
        r = requests.get(
            url,
            timeout=20
        )

        if r.status_code == 404:
            print(
                f"[WARN] OpenAlex has no record: {doi}"
            )

            return None

        r.raise_for_status()

        return r.json()

    except Exception as e:
        print(
            f"[WARN] OpenAlex lookup failed: {e}"
        )

        return None


def audit_publication(pub):
    errors = []
    warnings = []

    title = pub.get("title")
    doi = pub.get("doi")
    author_str = extract_author_names(pub)

    print("\n----------------------------------------")
    print(title)
    print("----------------------------------------")

    if not title:
        errors.append("Missing title")

    if not doi:
        errors.append("Missing DOI")

    if not author_str:
        warnings.append("Missing author")

    crossref = None

    if doi:
        crossref = crossref_lookup(doi)

    if crossref:
        cr_title = crossref.get(
            "title",
            [""]
        )[0]

        print(
            "[INFO] Crossref title:",
            cr_title
        )

        if normalize(title) != normalize(cr_title):
            warnings.append(
                "Title mismatch with Crossref"
            )

        cr_authors = crossref.get(
            "author",
            []
        )

        if cr_authors:
            cr_family = cr_authors[0].get(
                "family",
                ""
            )

            if author_str and normalize(
                cr_family
            ) not in normalize(author_str):
                warnings.append(
                    "Author mismatch with Crossref"
                )

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

        if normalize(title) != normalize(oa_title):
            warnings.append(
                "Title mismatch with OpenAlex"
            )

    else:
        warnings.append(
            "Publication not yet found in OpenAlex"
        )

    return errors, warnings


def main():
    print("\n")
    print("========================================")
    print(" SCHOLARLY METADATA AUDIT")
    print("========================================")

    if not METADATA.exists():
        print(
            "[ERROR] Missing "
            "scholarly/publications.json"
        )

        sys.exit(1)

    metadata = load_json(METADATA)

    publications = metadata.get(
        "publications",
        []
    )

    total_errors = 0
    total_warnings = 0

    report = []

    for pub in publications:
        errors, warnings = audit_publication(
            pub
        )

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
        "schema_version": "1.0",
        "publications": len(publications),
        "errors": total_errors,
        "warnings": total_warnings,
        "results": report
    }

    output = (
        REPORT_DIR /
        "scholarly-audit.json"
    )

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
        "Publications:",
        len(publications)
    )

    print(
        "Errors:",
        total_errors
    )

    print(
        "Warnings:",
        total_warnings
    )

    if total_errors:
        print(
            "\nAUDIT STATUS: FAIL"
        )

        sys.exit(1)

    print(
        "\nAUDIT STATUS: PASS"
    )


if __name__ == "__main__":
    main()
