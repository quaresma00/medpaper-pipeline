"""Reference-integrity checks.

Enforces: every citation in the manuscript resolves to a bib entry that was
retrieved from a real API and independently verified. A citekey that is not in
verified.json with verified=true is treated as fabricated.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from . import Ctx, Result, check

BIB = "06_refs/refs.bib"
RIS = "06_refs/refs.ris"
LIB = "06_refs/library.json"
VER = "06_refs/verified.json"

FENCE_RE = re.compile(r"```.*?```", re.S)
BRACKET_CITE_RE = re.compile(r"\[([^\]]*@[^\]]*)\]")
KEY_RE = re.compile(r"@([A-Za-z][\w:.#$%&+?<>~/-]*)")
BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s}]+)\s*,", re.M)


def citekeys(text: str) -> list[str]:
    text = FENCE_RE.sub(" ", text)
    keys: list[str] = []
    for group in BRACKET_CITE_RE.findall(text):
        keys.extend(KEY_RE.findall(group))
    # bare in-text citations: "as @smith2020 showed"
    stripped = BRACKET_CITE_RE.sub(" ", text)
    keys.extend(KEY_RE.findall(stripped))
    return keys


def bib_keys(text: str) -> set[str]:
    return {k for _, k in BIB_ENTRY_RE.findall(text)}


def _verified_data(ctx: Ctx) -> dict:
    if not ctx.p(VER).exists():
        return {}
    try:
        return ctx.read_json(VER)
    except Exception:  # noqa: BLE001
        return {}


def _verified_map(ctx: Ctx) -> dict:
    data = _verified_data(ctx)
    return data.get("records", data if isinstance(data, dict) else {})


def _library_entries_map(ctx: Ctx) -> dict[str, dict]:
    if not ctx.p(LIB).exists():
        return {}
    try:
        data = ctx.read_json(LIB)
        return {e["citekey"]: e for e in data.get("entries", []) if e.get("citekey")}
    except Exception:  # noqa: BLE001
        return {}


def detect_bypass_scripts(ctx: Ctx) -> list[str]:
    """Detect unauthorized bypass or tampering scripts trying to forge verified.json."""
    suspicious = []
    root = ctx.root
    candidates = []
    try:
        for p in root.glob("*.py"):
            if p.name not in ("bootstrap.py",):
                candidates.append(p)
        for p in ctx.project.glob("**/*.py"):
            candidates.append(p)
    except Exception:
        pass

    tamper_patterns = [
        re.compile(r'["\']verified["\']\s*:\s*True', re.I),
        re.compile(r'verified\.json', re.I),
        re.compile(r'["\']records["\']\s*\[.*?\]\s*=', re.I),
    ]

    for f in candidates:
        if "tools" in f.parts or ".venv" in f.parts or "scratch" in f.parts:
            continue
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            matches = sum(1 for pat in tamper_patterns if pat.search(txt))
            if matches >= 2 or ("verified.json" in txt and ("open(" in txt or "write_text" in txt)):
                suspicious.append(str(f.relative_to(root) if root in f.parents else f.name))
        except OSError:
            pass

    return suspicious


def verify_cache_evidence(ctx: Ctx, citekey: str, ver_entry: dict, lib_entry: dict) -> list[str]:
    """Validate that a citekey has a genuine NCBI XML cache file and matches the record."""
    cache_rel = ver_entry.get("cache_file") or lib_entry.get("cache_file")
    if not cache_rel:
        return [f"@{citekey}: no 'cache_file' proof-of-retrieval recorded"]

    cache_path = ctx.p(cache_rel)
    if not cache_path.exists() or cache_path.stat().st_size == 0:
        return [f"@{citekey}: raw NCBI cache file '{cache_rel}' is missing or empty on disk"]

    pmid = str(ver_entry.get("pmid") or lib_entry.get("pmid") or "").strip()
    doi = str(ver_entry.get("doi") or lib_entry.get("doi") or "").strip().lower()

    # Check for obvious fabricated fake DOIs
    if any(fake_word in doi for fake_word in ("fake", "dummy", "test", "example", "placeholder", "todo")):
        return [f"@{citekey}: contains fabricated/placeholder DOI '{doi}'"]

    # Parse raw XML cache to confirm PMID really exists inside the NCBI response
    if pmid:
        try:
            xml_text = cache_path.read_text(encoding="utf-8", errors="replace")
            if f"<PMID>{pmid}</PMID>" not in xml_text and f"<PMID Version=" not in xml_text:
                root = ET.fromstring(xml_text)
                pmids_in_cache = {t.text.strip() for t in root.findall(".//PMID") if t.text}
                if pmid not in pmids_in_cache:
                    return [f"@{citekey}: PMID {pmid} is absent from raw NCBI response {cache_rel} (fabricated record)"]
        except Exception as exc:
            return [f"@{citekey}: cannot parse raw NCBI cache {cache_rel}: {exc}"]

    return []


@check("citekeys_resolve")
def citekeys_resolve(ctx: Ctx) -> Result:
    paths = ctx.spec.get("paths", [])
    allow_unverified = bool(ctx.spec.get("allow_unverified", False))
    present = [p for p in paths if ctx.p(p).exists()]
    if not present:
        return Result(False, "citekeys_resolve", "none of the target files exist: " + ", ".join(paths))

    # 1. Anti-tampering guard: detect unauthorized bypass scripts in project or workspace
    bypass_scripts = detect_bypass_scripts(ctx)
    if bypass_scripts:
        return Result(
            False,
            "citekeys_resolve",
            f"FATAL ACADEMIC INTEGRITY VIOLATION: Unauthorized bypass script(s) detected: {', '.join(bypass_scripts)}. "
            "Never bypass tools/pubmed/ or forge verified.json.",
            [
                "Delete any custom bypass scripts immediately.",
                "To add legitimate literature: uv run python tools/pubmed/client.py search --query '...'",
                "Then add real PMIDs: uv run python tools/pubmed/build_library.py --add-ids <PMID>",
                "Then verify legitimately: uv run python tools/pubmed/verify.py",
                "Then export: uv run python tools/pubmed/build_library.py --export",
            ],
        )

    used: dict[str, list[str]] = {}
    for rel in present:
        for k in citekeys(ctx.read(rel)):
            used.setdefault(k, []).append(rel)
    if not used:
        return Result(
            False,
            "citekeys_resolve",
            "no pandoc citations found in " + ", ".join(present),
            ["Cite with pandoc markers: [@author2023] or [@a2023; @b2021]."],
        )

    have_bib = ctx.p(BIB).exists()
    known = bib_keys(ctx.read(BIB)) if have_bib else set()
    raw_ver_data = _verified_data(ctx)
    ver = _verified_map(ctx)
    lib_map = _library_entries_map(ctx)

    if not have_bib and allow_unverified:
        return Result(
            True,
            "citekeys_resolve",
            f"{len(used)} citekey(s); refs.bib not built yet (permitted at this stage)",
            severity="warn",
        )

    # 2. Validate cryptographic provenance signature of verified.json
    if raw_ver_data and not allow_unverified:
        try:
            sys.path.insert(0, str(ctx.root / "tools" / "pubmed"))
            from verify import verify_provenance_signature
            sig_ok, sig_reason = verify_provenance_signature(raw_ver_data, ctx.project)
            if not sig_ok:
                return Result(
                    False,
                    "citekeys_resolve",
                    f"FATAL INTEGRITY VIOLATION: verified.json signature verification failed: {sig_reason}. "
                    "File has been tampered with or modified outside tools/pubmed/verify.py.",
                    [
                        "Re-verify all entries with real NCBI API: uv run python tools/pubmed/verify.py",
                        "Never edit verified.json by hand or via custom scripts.",
                    ],
                )
        except Exception as e:
            return Result(
                False,
                "citekeys_resolve",
                f"Error validating verified.json provenance: {e}",
            )

    unknown = sorted(k for k in used if k not in known)
    unverified = sorted(
        k for k in used
        if k in known and not (ver.get(k, {}) or {}).get("verified") is True
    )

    # 3. Physical raw XML cache evidence check for each cited key
    evidence_problems = []
    if not allow_unverified:
        for k in sorted(used.keys()):
            v_rec = ver.get(k, {})
            l_rec = lib_map.get(k, {})
            errs = verify_cache_evidence(ctx, k, v_rec, l_rec)
            evidence_problems.extend(errs)

    problems = []
    if unknown:
        problems.append(f"{len(unknown)} citekey(s) absent from refs.bib: " + ", ".join(unknown[:8]))
    if unverified and not allow_unverified:
        problems.append(f"{len(unverified)} citekey(s) not verified: " + ", ".join(unverified[:8]))
    if evidence_problems:
        problems.append(f"Physical proof-of-retrieval failure ({len(evidence_problems)} issue(s)): " + "; ".join(evidence_problems[:4]))

    if problems:
        return Result(
            False,
            "citekeys_resolve",
            "; ".join(problems),
            [
                "STRICT PROTOCOL FOR ADDING CITATIONS (ZERO-FABRICATION POLICY):",
                "1. Search genuine PubMed records: uv run python tools/pubmed/client.py search --query '<term>'",
                "2. Add real PubMed ID to library: uv run python tools/pubmed/build_library.py --add-ids <PMID>",
                "3. Verify and sign: uv run python tools/pubmed/verify.py",
                "4. Export bib: uv run python tools/pubmed/build_library.py --export",
                "5. Cite the legitimate citekey in manuscript markdown.",
                "NEVER invent citations, fake DOIs, or modify verified.json directly.",
            ],
        )
    return Result(
        True,
        "citekeys_resolve",
        f"{len(used)} distinct citekey(s), all present in refs.bib, verified, and tied to authentic NCBI XML payloads"
    )


@check("citation_count")
def citation_count(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    if not ctx.p(rel).exists():
        return Result(False, "citation_count", f"{rel} missing")
    n = len(set(citekeys(ctx.read(rel))))
    lo, hi = ctx.spec_bound("min"), ctx.spec_bound("max")
    if lo is not None and n < lo:
        return Result(False, "citation_count", f"{rel}: {n} distinct references, target >= {lo}")
    if hi is not None and n > hi:
        return Result(False, "citation_count", f"{rel}: {n} distinct references, target <= {hi}")
    return Result(True, "citation_count", f"{rel}: {n} distinct references (target {lo}-{hi})")


@check("refs_library")
def refs_library(ctx: Ctx) -> Result:
    if not ctx.p(LIB).exists():
        return Result(False, "refs_library", f"{LIB} missing")
    try:
        lib = ctx.read_json(LIB)
    except json.JSONDecodeError as exc:
        return Result(False, "refs_library", f"{LIB} invalid JSON: {exc}")
    entries = lib.get("entries", [])
    lo = ctx.spec.get("min_entries", ctx.target("reflib_min", 45))
    hi = ctx.spec.get("max_entries", ctx.target("reflib_max", 60))

    problems = []
    if len(entries) < lo:
        problems.append(f"{len(entries)} entries, need >= {lo}")
    if hi and len(entries) > hi:
        problems.append(f"{len(entries)} entries, allowed <= {hi}")

    if ctx.spec.get("require_abstract", True):
        no_abs = [e.get("citekey", "?") for e in entries if not (e.get("abstract") or "").strip()]
        if no_abs:
            problems.append(
                f"{len(no_abs)} entry/entries without an abstract (must be removed): " + ", ".join(no_abs[:6])
            )
    missing_id = [e.get("citekey", "?") for e in entries if not (e.get("pmid") or e.get("doi"))]
    if missing_id:
        problems.append(f"{len(missing_id)} entry/entries with neither PMID nor DOI: " + ", ".join(missing_id[:6]))

    if ctx.spec.get("require_verified", True):
        raw_ver_data = _verified_data(ctx)
        if raw_ver_data:
            try:
                sys.path.insert(0, str(ctx.root / "tools" / "pubmed"))
                from verify import verify_provenance_signature
                sig_ok, sig_reason = verify_provenance_signature(raw_ver_data, ctx.project)
                if not sig_ok:
                    problems.append(f"verified.json signature invalid ({sig_reason}); tampering detected")
            except Exception as e:
                problems.append(f"error validating verified.json signature: {e}")

        ver = _verified_map(ctx)
        unver = [
            e.get("citekey", "?") for e in entries
            if not (ver.get(e.get("citekey", ""), {}) or {}).get("verified") is True
        ]
        if unver:
            problems.append(f"{len(unver)} entry/entries unverified: " + ", ".join(unver[:6]))

        # Cache file existence check
        missing_caches = [
            e.get("citekey", "?") for e in entries
            if not e.get("cache_file") or not ctx.p(e.get("cache_file", "")).exists()
        ]
        if missing_caches:
            problems.append(f"{len(missing_caches)} entry/entries missing raw NCBI XML cache: " + ", ".join(missing_caches[:4]))

    dupes = _dupes([e.get("citekey") for e in entries])
    if dupes:
        problems.append("duplicate citekeys: " + ", ".join(dupes[:6]))

    if problems:
        return Result(
            False,
            "refs_library",
            "; ".join(problems),
            [
                "Rebuild with: python tools/pubmed/build_library.py --topic \"...\" --target 50",
                "Entries without abstracts must be dropped, not padded with a summary you wrote.",
            ],
        )
    return Result(True, "refs_library", f"{len(entries)} verified entries, all with abstracts and an ID")


@check("bib_ris_match_library")
def bib_ris_match_library(ctx: Ctx) -> Result:
    for rel in (LIB, BIB, RIS):
        if not ctx.p(rel).exists():
            return Result(False, "bib_ris_match_library", f"{rel} missing")
    lib = ctx.read_json(LIB)
    lib_keys = {e.get("citekey") for e in lib.get("entries", []) if e.get("citekey")}
    bkeys = bib_keys(ctx.read(BIB))
    n_ris = len(re.findall(r"^TY\s+-\s+", ctx.read(RIS), re.M))
    problems = []
    if lib_keys != bkeys:
        only_lib = sorted(lib_keys - bkeys)[:5]
        only_bib = sorted(bkeys - lib_keys)[:5]
        problems.append(f"library/bib mismatch (library-only: {only_lib}, bib-only: {only_bib})")
    if n_ris != len(lib_keys):
        problems.append(f"RIS has {n_ris} records vs {len(lib_keys)} library entries")
    if problems:
        return Result(
            False,
            "bib_ris_match_library",
            "; ".join(problems),
            ["Regenerate both formats from library.json rather than editing them by hand."],
        )
    return Result(True, "bib_ris_match_library", f"library / bib / ris agree on {len(lib_keys)} records")


@check("pubmed_cache_fresh")
def pubmed_cache_fresh(ctx: Ctx) -> Result:
    """Proof-of-retrieval: a real search happened and its payload is on disk."""
    rel = ctx.spec.get("manifest", "06_refs/cache/scan_manifest.json")
    if not ctx.p(rel).exists():
        return Result(
            False,
            "pubmed_cache_fresh",
            f"{rel} missing - no evidence any literature search was actually run",
            ["Search via: python tools/pubmed/client.py search --query \"...\" (writes the manifest and caches raw payloads)"],
        )
    try:
        man = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "pubmed_cache_fresh", f"{rel} invalid JSON: {exc}")
    queries = man.get("queries", [])
    min_q = ctx.spec.get("min_queries", 3)
    min_hits = ctx.spec.get("min_hits", 20)

    uniq_q = {q.get("query", "").strip().lower() for q in queries if q.get("query")}
    pmids: set[str] = set()
    missing_cache = []
    for q in queries:
        pmids.update(str(x) for x in q.get("ids", []))
        cf = q.get("cache_file")
        if cf and not ctx.p(cf).exists():
            missing_cache.append(cf)

    problems = []
    if len(uniq_q) < min_q:
        problems.append(f"{len(uniq_q)} distinct queries, need >= {min_q}")
    if len(pmids) < min_hits:
        problems.append(f"{len(pmids)} unique records retrieved, need >= {min_hits}")
    if missing_cache:
        problems.append(f"{len(missing_cache)} cached payload(s) missing: " + ", ".join(missing_cache[:4]))
    if problems:
        return Result(False, "pubmed_cache_fresh", "; ".join(problems))
    return Result(
        True,
        "pubmed_cache_fresh",
        f"{len(uniq_q)} queries, {len(pmids)} unique records, payloads cached",
    )


@check("deepread_complete")
def deepread_complete(ctx: Ctx) -> Result:
    rel = "06_refs/deepread/deepread_index.json"
    if not ctx.p(rel).exists():
        return Result(False, "deepread_complete", f"{rel} missing")
    try:
        idx = ctx.read_json(rel)
    except json.JSONDecodeError as exc:
        return Result(False, "deepread_complete", f"{rel} invalid JSON: {exc}")
    sel = idx.get("selected", [])
    want = ctx.target("deepread_count", 5)
    problems = []
    if len(sel) < max(3, want - 1):
        problems.append(f"{len(sel)} paper(s) selected, target ~{want}")

    lib_keys = set()
    if ctx.p(LIB).exists():
        try:
            lib_keys = {e.get("citekey") for e in ctx.read_json(LIB).get("entries", [])}
        except Exception:  # noqa: BLE001
            pass

    for item in sel:
        ck = item.get("citekey", "?")
        if lib_keys and ck not in lib_keys:
            problems.append(f"{ck} is not in library.json")
        if not item.get("reason"):
            problems.append(f"{ck}: no selection reason recorded")
        src = item.get("fulltext")
        if not src:
            problems.append(f"{ck}: no full-text source recorded")
        elif not str(src).startswith("http") and not ctx.p(str(src)).exists():
            problems.append(f"{ck}: full text {src} not on disk")
        notes = item.get("notes")
        if not notes:
            problems.append(f"{ck}: no notes file")
        else:
            np = ctx.p(str(notes))
            if not np.exists():
                problems.append(f"{ck}: notes file {notes} missing")
            elif len(np.read_text(encoding="utf-8", errors="replace").strip()) < 400:
                problems.append(f"{ck}: notes too thin to have been a real read")
    if problems:
        return Result(
            False,
            "deepread_complete",
            "; ".join(problems[:8]),
            ["Fetch open-access full text with: python tools/pubmed/fulltext.py --citekey KEY"],
        )
    return Result(True, "deepread_complete", f"{len(sel)} paper(s) fetched and read with notes on disk")


@check("deepread_cited")
def deepread_cited(ctx: Ctx) -> Result:
    rel = ctx.spec["path"]
    idx_rel = "06_refs/deepread/deepread_index.json"
    if not ctx.p(rel).exists() or not ctx.p(idx_rel).exists():
        return Result(False, "deepread_cited", "discussion or deepread index missing")
    sel = [i.get("citekey") for i in ctx.read_json(idx_rel).get("selected", []) if i.get("citekey")]
    used = set(citekeys(ctx.read(rel)))
    absent = [k for k in sel if k not in used]
    if absent:
        return Result(
            False,
            "deepread_cited",
            "deep-read paper(s) never cited in the Discussion: " + ", ".join(absent),
            ["If a paper turned out irrelevant, drop it from deepread_index.json and record why."],
        )
    return Result(True, "deepread_cited", f"all {len(sel)} deep-read paper(s) engaged in the Discussion")


@check("guidelines_sourced")
def guidelines_sourced(ctx: Ctx) -> Result:
    tj, gx = "08_submission/target_journal.json", "08_submission/guidelines_extract.md"
    for rel in (tj, gx):
        if not ctx.p(rel).exists():
            return Result(False, "guidelines_sourced", f"{rel} missing")
    meta = ctx.read_json(tj)
    url = (meta.get("guidelines_url") or "").strip()
    text = ctx.read(gx)
    problems = []
    if not url.startswith("http"):
        problems.append("target_journal.json has no usable guidelines_url")
    elif url not in text:
        problems.append("guidelines_extract.md does not cite the exact guidelines_url it came from")
    if not (meta.get("guidelines_fetched_at") or "").strip():
        problems.append("guidelines_fetched_at not recorded")
    snapshots = ctx.glob("08_submission/cache/*")
    if not snapshots:
        problems.append("no raw snapshot under 08_submission/cache/ - guidelines were not actually fetched")
    for need in ("Word limits", "Reference style", "Figure", "Table", "Required statements", "Submission items"):
        if need.lower() not in text.lower():
            problems.append(f"guidelines_extract.md does not cover: {need}")
    if problems:
        return Result(
            False,
            "guidelines_sourced",
            "; ".join(problems[:8]),
            ["Fetch the live author instructions and quote the constraints, do not recall them from memory."],
        )
    return Result(True, "guidelines_sourced", "guidelines fetched, snapshotted and fully extracted")


def _dupes(items) -> list[str]:
    seen, out = set(), []
    for x in items:
        if x in seen and x not in out:
            out.append(x)
        seen.add(x)
    return out
