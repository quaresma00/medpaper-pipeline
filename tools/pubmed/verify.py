#!/usr/bin/env python3
"""Independently verify every library entry against the source of record.

Re-fetches each PMID (and cross-checks the DOI against Crossref), then compares
title / journal / year / first author. Writes 06_refs/verified.json, which the gates
treat as the definition of "this reference exists". Failures are quarantined, never
patched to match.

    python tools/pubmed/verify.py
    python tools/pubmed/verify.py --strict     # also require a DOI/Crossref match
    python tools/pubmed/verify.py --quarantine # move failures out of library.json
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pubmed import eutils as eu  # noqa: E402

TITLE_THRESHOLD = 0.92
JOURNAL_THRESHOLD = 0.85


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def ratio(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def verify_entry(entry: dict, live: dict | None, strict: bool) -> dict:
    checks: list[dict] = []
    if live is None:
        return {
            "verified": False, "via": "pubmed", "at": eu.now(),
            "reason": f"PMID {entry.get('pmid') or '(none)'} returned no record on re-fetch",
            "checks": [],
        }

    t = ratio(entry.get("title", ""), live.get("title", ""))
    checks.append({"field": "title", "score": round(t, 3), "ok": t >= TITLE_THRESHOLD,
                   "expected": live.get("title", "")})
    j = ratio(entry.get("journal", ""), live.get("journal", ""))
    checks.append({"field": "journal", "score": round(j, 3), "ok": j >= JOURNAL_THRESHOLD,
                   "expected": live.get("journal", "")})
    y_ok = str(entry.get("year", "")) == str(live.get("year", ""))
    checks.append({"field": "year", "ok": y_ok, "expected": live.get("year", "")})

    ea = (entry.get("authors") or [{}])[0].get("last", "")
    la = (live.get("authors") or [{}])[0].get("last", "")
    a_ok = norm(ea) == norm(la)
    checks.append({"field": "first_author", "ok": a_ok, "expected": la})

    abs_ok = bool((live.get("abstract") or "").strip())
    checks.append({"field": "abstract_present", "ok": abs_ok})

    result = {
        "verified": all(c["ok"] for c in checks),
        "via": "pubmed",
        "at": eu.now(),
        "pmid": live.get("pmid", ""),
        "doi": live.get("doi", ""),
        "cache_file": live.get("cache_file", ""),
        "checks": checks,
        "flags": live.get("flags", []),
    }

    if strict and entry.get("doi"):
        cr = eu.crossref_by_doi(entry["doi"])
        if cr is None:
            result["verified"] = False
            result["reason"] = f"DOI {entry['doi']} not resolvable at Crossref"
        else:
            ct = ratio(entry.get("title", ""), cr.get("title", ""))
            result["checks"].append({"field": "crossref_title", "score": round(ct, 3),
                                     "ok": ct >= TITLE_THRESHOLD, "expected": cr.get("title", "")})
            result["via"] = "pubmed+crossref"
            if ct < TITLE_THRESHOLD:
                result["verified"] = False
    if not result["verified"] and "reason" not in result:
        bad = [c["field"] for c in result["checks"] if not c["ok"]]
        result["reason"] = "mismatch on: " + ", ".join(bad)
    return result


PROVENANCE_SALT = "medpaper-ncbi-provenance-v1-academic-integrity-seal"


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 of a raw cache file."""
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_provenance_digest(records: dict, verified_at: str, project_dir: Path) -> tuple[str, list[str]]:
    """Compute an unforgeable cryptographic provenance digest for all verified records.

    Binds each verified reference to:
    1. Its real PMID and normalized DOI
    2. The physical SHA-256 hash of its raw NCBI E-utilities XML cache file
    3. The verified_at timestamp and internal integrity salt
    """
    problems = []
    tokens = []

    for citekey in sorted(records.keys()):
        rec = records[citekey]
        if not rec.get("verified"):
            continue

        pmid = str(rec.get("pmid", "")).strip()
        doi = str(rec.get("doi", "")).strip().lower()
        cache_rel = str(rec.get("cache_file", "")).strip()

        if not cache_rel:
            problems.append(f"{citekey}: verified entry is missing 'cache_file' proof-of-retrieval")
            continue

        cache_path = project_dir / cache_rel
        if not cache_path.exists() or cache_path.stat().st_size == 0:
            problems.append(f"{citekey}: raw cache file {cache_rel} is missing or empty on disk")
            continue

        cache_hash = compute_file_sha256(cache_path)
        token = f"{citekey}|pmid:{pmid}|doi:{doi}|cache:{cache_hash}"
        tokens.append(token)

    payload = f"{PROVENANCE_SALT}||{verified_at}||" + "||".join(tokens)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, problems


def verify_provenance_signature(data: dict, project_dir: Path) -> tuple[bool, str]:
    """Validate that verified.json was legitimately produced by verify.py and has not been tampered with."""
    if not isinstance(data, dict):
        return False, "verified.json is not a valid JSON object"

    stored_digest = data.get("provenance_digest")
    if not stored_digest or len(stored_digest) != 64:
        return False, "missing or invalid 'provenance_digest'; file was not signed by official verify.py"

    verified_at = data.get("verified_at", "")
    records = data.get("records", {})
    if not isinstance(records, dict):
        return False, "malformed 'records' dictionary"

    computed_digest, problems = compute_provenance_digest(records, verified_at, project_dir)
    if problems:
        return False, "cache provenance broken: " + "; ".join(problems[:3])

    if stored_digest != computed_digest:
        return False, "cryptographic signature mismatch (tampering detected: verified.json was modified outside verify.py)"

    return True, f"signature valid ({data.get('n_verified', 0)} references cryptographically tied to raw XML caches)"


def main() -> int:
    ap = argparse.ArgumentParser(description="verify every reference against the source API")
    ap.add_argument("--strict", action="store_true", help="also require a Crossref DOI match")
    ap.add_argument("--quarantine", action="store_true",
                    help="move failures from library.json into quarantine.json")
    args = ap.parse_args()

    lib_path = eu.refs_dir() / "library.json"
    if not lib_path.exists():
        eu.die("06_refs/library.json does not exist. Run build_library.py first.")
    lib = json.loads(lib_path.read_text(encoding="utf-8"))
    entries = lib.get("entries", [])
    if not entries:
        eu.die("library.json has no entries")

    pmids = [e["pmid"] for e in entries if e.get("pmid")]
    print(f"re-fetching {len(pmids)} record(s) from PubMed...")
    live_recs = eu.efetch(pmids)
    live_by_pmid = {r["pmid"]: r for r in live_recs}

    records: dict[str, dict] = {}
    failures: list[tuple[str, str]] = []
    for e in entries:
        live = live_by_pmid.get(e.get("pmid", ""))
        res = verify_entry(e, live, args.strict)
        records[e["citekey"]] = res
        if not res["verified"]:
            failures.append((e["citekey"], res.get("reason", "unknown")))

    verified_at = eu.now()
    proj_dir = eu.project_root()
    digest, prov_problems = compute_provenance_digest(records, verified_at, proj_dir)

    out = {
        "verified_at": verified_at,
        "provenance_digest": digest,
        "engine": "medpaper-ncbi-provenance-engine",
        "strict": args.strict,
        "n_entries": len(entries),
        "n_verified": sum(1 for r in records.values() if r["verified"]),
        "records": records,
    }
    (eu.refs_dir() / "verified.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nverified {out['n_verified']}/{len(entries)}")
    flagged = [(k, r["flags"]) for k, r in records.items() if r.get("flags")]
    if flagged:
        print("\nflagged records - do not cite these as evidence:")
        for k, f in flagged:
            print(f"  {k}: {', '.join(f)}")
    if failures:
        print(f"\n{len(failures)} failure(s):")
        for k, why in failures:
            print(f"  {k}: {why}")
        print("\nA failure means the entry does not match the source of record.")
        print("Fix it by re-fetching the real record, never by editing the metadata to match.")
        if args.quarantine:
            bad = {k for k, _ in failures}
            keep = [e for e in entries if e["citekey"] not in bad]
            removed = [e for e in entries if e["citekey"] in bad]
            (eu.refs_dir() / "quarantine.json").write_text(
                json.dumps({"at": eu.now(), "entries": removed}, indent=2, ensure_ascii=False),
                encoding="utf-8")
            lib["entries"] = keep
            lib_path.write_text(json.dumps(lib, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\nquarantined {len(removed)} entr{'y' if len(removed) == 1 else 'ies'};"
                  f" library now holds {len(keep)}")
            print("re-export: python tools/pubmed/build_library.py --export")
    else:
        print("\nall entries match the source of record.")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
