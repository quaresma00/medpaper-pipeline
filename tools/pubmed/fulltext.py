#!/usr/bin/env python3
"""Fetch open-access full text for the deep-read papers.

Legal open-access routes only, tried in order: Europe PMC / PMC OA -> Unpaywall ->
OpenAlex -> Crossref link. Paywalled papers are recorded as paywalled; they are never
silently treated as read.

    python tools/pubmed/fulltext.py --citekey smith2023 --citekey lee2021
    python tools/pubmed/fulltext.py --all-deepread
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
UNPAYWALL = "https://api.unpaywall.org/v2"
OPENALEX = "https://api.openalex.org/works"


def out_dir() -> Path:
    d = eu.project_root() / "06_refs" / "fulltext"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _save(name: str, blob: bytes) -> str:
    p = out_dir() / name
    p.write_bytes(blob)
    return f"06_refs/fulltext/{name}"


# ---------------------------------------------------------------------------
def try_europepmc(entry: dict) -> dict | None:
    pmid, pmcid = entry.get("pmid"), entry.get("pmcid")
    if not pmcid and pmid:
        try:
            raw = eu.http_get(f"{EPMC}/search",
                              {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"})
            hits = json.loads(raw).get("resultList", {}).get("result", [])
            if hits:
                pmcid = hits[0].get("pmcid") or ""
                if hits[0].get("isOpenAccess") != "Y" and not pmcid:
                    return None
        except Exception:  # noqa: BLE001
            return None
    if not pmcid:
        return None
    pmcid = pmcid if pmcid.upper().startswith("PMC") else f"PMC{pmcid}"
    for kind, url, ext in (
        ("xml", f"{EPMC}/{pmcid}/fullTextXML", "xml"),
        ("pdf", f"{EPMC}/{pmcid}/pdf", "pdf"),
    ):
        try:
            blob = eu.http_get(url)
        except Exception:  # noqa: BLE001
            continue
        if len(blob) < 2000:
            continue
        rel = _save(f"{entry['citekey']}.{ext}", blob)
        return {"route": f"europepmc-{kind}", "access": "oa", "fulltext": rel,
                "bytes": len(blob), "pmcid": pmcid}
    return None


def try_unpaywall(entry: dict) -> dict | None:
    doi, email = entry.get("doi"), eu.api_email()
    if not doi or not email:
        return None
    try:
        raw = eu.http_get(f"{UNPAYWALL}/{urllib.parse.quote(doi)}", {"email": email})
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    loc = data.get("best_oa_location") or {}
    url = loc.get("url_for_pdf") or loc.get("url")
    if not url:
        return None
    try:
        blob = eu.http_get(url)
    except Exception:  # noqa: BLE001
        return {"route": "unpaywall-link", "access": "oa", "fulltext": url,
                "note": "OA landing page found but the file could not be downloaded here"}
    ext = "pdf" if blob[:4] == b"%PDF" else "html"
    return {"route": "unpaywall", "access": "oa",
            "fulltext": _save(f"{entry['citekey']}.{ext}", blob), "bytes": len(blob),
            "license": loc.get("license"), "version": loc.get("version")}


def try_openalex(entry: dict) -> dict | None:
    doi = entry.get("doi")
    if not doi:
        return None
    try:
        raw = eu.http_get(f"{OPENALEX}/doi:{urllib.parse.quote(doi)}",
                          {"mailto": eu.api_email() or ""})
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    loc = data.get("best_oa_location") or {}
    url = loc.get("pdf_url") or loc.get("landing_page_url")
    if not url:
        return None
    try:
        blob = eu.http_get(url)
        ext = "pdf" if blob[:4] == b"%PDF" else "html"
        return {"route": "openalex", "access": "oa",
                "fulltext": _save(f"{entry['citekey']}.{ext}", blob), "bytes": len(blob)}
    except Exception:  # noqa: BLE001
        return {"route": "openalex-link", "access": "oa", "fulltext": url}


ROUTES = (try_europepmc, try_unpaywall, try_openalex)


def fetch_one(entry: dict) -> dict:
    for fn in ROUTES:
        try:
            res = fn(entry)
        except Exception as exc:  # noqa: BLE001
            res = None
            print(f"    {fn.__name__} raised {type(exc).__name__}: {exc}")
        if res:
            return res
    doi = entry.get("doi")
    return {
        "route": "none", "access": "paywalled",
        "fulltext": f"https://doi.org/{doi}" if doi else "",
        "note": "no open-access copy found. Use your institutional access, or rely on the "
                "abstract and say so explicitly in the deep-read notes.",
    }


NOTES_TEMPLATE = """# {citekey} - {short_title}

Source: {source}
Access: {access} (route: {route})
PMID {pmid} | DOI {doi}

## Design and population

## What they did differently from us

## Their key numbers

## How this supports or contradicts our finding

## What a reviewer would take from this
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="fetch open-access full text for deep reading")
    ap.add_argument("--citekey", action="append", default=[])
    ap.add_argument("--all-deepread", action="store_true",
                    help="fetch everything listed in deepread_index.json")
    ap.add_argument("--no-stub", action="store_true", help="do not create the notes stub")
    args = ap.parse_args()

    lib_path = eu.refs_dir() / "library.json"
    if not lib_path.exists():
        eu.die("06_refs/library.json missing. Build the library first (S13).")
    entries = {e["citekey"]: e for e in json.loads(lib_path.read_text(encoding="utf-8")).get("entries", [])}

    keys = list(args.citekey)
    dr_path = eu.project_root() / "06_refs" / "deepread" / "deepread_index.json"
    if args.all_deepread:
        if not dr_path.exists():
            eu.die("deepread_index.json missing; pass --citekey instead")
        keys += [i["citekey"] for i in json.loads(dr_path.read_text(encoding="utf-8")).get("selected", [])]
    if not keys:
        eu.die("give at least one --citekey (or --all-deepread)")

    results = {}
    for key in dict.fromkeys(keys):
        entry = entries.get(key)
        if not entry:
            print(f"{key}: not in library.json - add it before deep-reading")
            continue
        print(f"{key}: {entry.get('title', '')[:70]}")
        res = fetch_one(entry)
        results[key] = res
        print(f"    -> {res['route']} / {res['access']} / {res.get('fulltext', '')}")
        if res.get("note"):
            print(f"       {res['note']}")

        if not args.no_stub:
            notes = eu.project_root() / "06_refs" / "deepread" / f"{key}.md"
            notes.parent.mkdir(parents=True, exist_ok=True)
            if not notes.exists():
                notes.write_text(NOTES_TEMPLATE.format(
                    citekey=key,
                    short_title=re.sub(r"\s+", " ", entry.get("title", ""))[:80],
                    source=f"{entry.get('journal', '')} {entry.get('year', '')}",
                    access=res["access"], route=res["route"],
                    pmid=entry.get("pmid", ""), doi=entry.get("doi", ""),
                ), encoding="utf-8")
                print(f"       notes stub: 06_refs/deepread/{key}.md")

    oa = sum(1 for r in results.values() if r["access"] == "oa")
    print(f"\n{oa}/{len(results)} available open access.")
    print("Fill in every notes file, then record them in 06_refs/deepread/deepread_index.json.")
    print("Notes under 400 characters are rejected by the S15 gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
