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
    归一化字符串，去除非字母数字字符，统一小写，提升标题匹配容错率。
    """
    if not text:
        return ""
    # 将 Unicode 换行符与多余空格压平
    text_clean = " ".join(str(text).split())
    return re.sub(r"[^a-z0-9]+", "", text_clean.lower())


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
        "User-Agent": (
            "ScholarlyAudit/1.0 "
            "(https://github.com; mailto:contact@scottsun.com)"
        )
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)

        if r.status_code == 404:
            print(f"[WARN] Crossref record not found for DOI: {doi}")
            return None

        r.raise_for_status()
        return r.json().get("message", {})

    except Exception as e:
        print(f"[WARN] Crossref lookup failed for {doi}: {e}")
        return None


def openalex_lookup(doi):
    # 使用 OpenAlex 官方标准的 Clean DOI URL 形式
    clean_doi = doi.replace("https://doi.org/", "").strip()
    url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"

    headers = {
        "User-Agent": (
            "ScholarlyAudit/1.0 "
            "(mailto:contact@scottsun.com)"
        )
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)

        if r.status_code == 404:
            print(f"[WARN] OpenAlex has no record for DOI: {clean_doi}")
            return None

        r.raise_for_status()
        return r.json()

    except Exception as e:
        print(f"[WARN] OpenAlex lookup failed for {clean_doi}: {e}")
        return None


def audit_citation_cff():
    """审计 CITATION.cff 文件的存在性与 YAML 格式解析"""
    if not CITATION.exists():
        print("[WARN] CITATION.cff is missing at repository root")
        return False, ["CITATION.cff missing"]

    try:
        with open(CITATION, "r", encoding="utf-8") as f:
            cff_data = yaml.safe_load(f)
            if not isinstance(cff_data, dict):
                return False, ["CITATION.cff format invalid"]
            print("[PASS] CITATION.cff loaded and validated")
            return True, []
    except Exception as e:
        print(f"[ERROR] Failed to parse CITATION.cff: {e}")
        return False, [f"CITATION.cff parse error: {e}"]


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

    if not author_str:
        warnings.append("Missing author")

    crossref = None
    if doi:
        crossref = crossref_lookup(doi)

    if crossref:
        cr_title_list = crossref.get("title", [])
        cr_title = cr_title_list[0] if cr_title_list else ""

        print(f"[INFO] Crossref title: {cr_title}")

        if title and cr_title and normalize(title) != normalize(cr_title):
            warnings.append("Title mismatch with Crossref")

        cr_authors = crossref.get("author", [])
        if cr_authors:
            cr_family = cr_authors[0].get("family", "")
            if author_str and cr_family and normalize(cr_family) not in normalize(author_str):
                warnings.append("Author mismatch with Crossref")
    else:
        warnings.append("Publication record pending or not in Crossref")

    openalex = None
    if doi:
        openalex = openalex_lookup(doi)

    if openalex:
        print("[PASS] OpenAlex record found")
        oa_title = openalex.get("display_name", "")

        if title and oa_title and normalize(title) != normalize(oa_title):
            warnings.append("Title mismatch with OpenAlex")
    else:
        warnings.append("Publication not yet indexed in OpenAlex")

    return errors, warnings


def main():
    print("\n========================================")
    print(" SCHOLARLY METADATA AUDIT")
    print("========================================")

    # 1. 验证元数据文件
    if not METADATA.exists():
        print(f"[ERROR] Missing required file: {METADATA}")
        sys.exit(1)

    # 2. 检查 CITATION.cff
    cff_ok, cff_errors = audit_citation_cff()

    metadata = load_json(METADATA)
    publications = metadata.get("publications", [])

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
        "schema_version": "1.0",
        "citation_cff_valid": cff_ok,
        "publications_count": len(publications),
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "results": report
    }

    output = REPORT_DIR / "scholarly-audit.json"

    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n========================================")
    print(" SUMMARY")
    print("========================================")
    print(f"CITATION.cff Status: {'PASS' if cff_ok else 'WARN/FAIL'}")
    print(f"Publications Audited: {len(publications)}")
    print(f"Total Errors:        {total_errors}")
    print(f"Total Warnings:      {total_warnings}")
    print(f"Report Generated:    {output}")

    if total_errors > 0:
        print("\nAUDIT STATUS: FAIL")
        sys.exit(1)

    print("\nAUDIT STATUS: PASS")


if __name__ == "__main__":
    main()
