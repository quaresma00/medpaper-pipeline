"""Data Acquisition Integrity, Anti-Truncation, and Full-Census Audit Checks.

Strictly eliminates model laziness, unapproved sampling, arbitrary truncation (e.g. nrows=,
head(), sample(), artificial limit= without pagination, loop break hacks), and ensures
100% census exhaustion against the declared protocol and physical disk payloads.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import Ctx, Result, check

# Patterns indicating rogue truncation, unapproved sampling, or artificial demo subsets
TRUNCATION_PATTERNS = [
    (
        re.compile(r"\bpd\.read_\w+\([^)]*?\bnrows\s*=\s*\d+", re.I),
        "pandas read_* with hardcoded 'nrows=' truncation parameter",
    ),
    (
        re.compile(r"\bread\.(?:csv|delim|table)\([^)]*?\bnrows\s*=\s*\d+", re.I),
        "R read.* with hardcoded 'nrows=' truncation parameter",
    ),
    (
        re.compile(r"\.(?:head|tail)\s*\(\s*\d+\s*\)", re.I),
        "arbitrary dataframe .head(N)/.tail(N) truncation used during data processing",
    ),
    (
        re.compile(r"\.(?:iloc|loc)\s*\[\s*:\s*\d+\s*\]", re.I),
        "arbitrary dataframe slice [:N] truncation used during data processing",
    ),
    (
        re.compile(r"\b(?:\.sample|sample)\s*\(\s*(?:n\s*=\s*\d+|frac\s*=\s*0?\.\d+)", re.I),
        "unapproved data sampling (.sample()) without declared statistical sampling design",
    ),
    (
        re.compile(r"\bif\s+.*?(?:count|page|len|idx|i|n|step|batch|rows?)\s*(?:>=|>|==)\s*\d+\s*:\s*break\b", re.I),
        "early-termination break in pagination loop (artificial loop cut-off)",
    ),
    (
        re.compile(r"#\s*(?:quick\s+test|test\s+only|sample\s+subset|demo\s+only|subset\s+for\s+test|dummy\s+data|toy\s+dataset)\b", re.I),
        "lazy/toy subset comment flag detected in production acquisition code",
    ),
]

# Pattern for API requests with small hardcoded limits lacking outer pagination loops
API_LIMIT_PATTERN = re.compile(r"\b(?:limit|pageSize|page_size|max_results)\s*=\s*(\d+)\b", re.I)


def scan_code_for_truncation(script_path: Path) -> list[str]:
    """Scan a Python or R script for rogue truncation, sample, or laziness patterns."""
    issues = []
    try:
        content = script_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [f"Cannot read {script_path.name}: {exc}"]

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            # Check comment for laziness tags
            for pat, desc in TRUNCATION_PATTERNS:
                if "comment flag" in desc and pat.search(stripped):
                    issues.append(f"{script_path.name}:L{line_idx}: {desc}: '{stripped}'")
            continue

        for pat, desc in TRUNCATION_PATTERNS:
            if "comment flag" in desc:
                continue
            if pat.search(line):
                issues.append(f"{script_path.name}:L{line_idx}: {desc}: '{stripped[:80]}'")

    # Check for multiline early break in loops
    multiline_break = re.compile(
        r"if\s+[^:\n]*(?:count|page|len|idx|i|n|step|batch|rows?|total)\s*(?:>=|>|==)\s*\d+\s*:\s*(?:\n\s*|\s+)break\b",
        re.I
    )
    for m in multiline_break.finditer(content):
        matched_snippet = re.sub(r"\s+", " ", m.group(0)).strip()
        issues.append(
            f"{script_path.name}: early-termination break in loop detected: '{matched_snippet}'. Artificial truncation is forbidden."
        )

    # Check for single-page API limit without pagination loop
    if API_LIMIT_PATTERN.search(content):
        matches = API_LIMIT_PATTERN.findall(content)
        for m in matches:
            val = int(m)
            if val <= 100:
                has_loop = bool(re.search(r"\b(?:while\s+|for\s+\w+\s+in\s+)", content))
                has_pagination_token = bool(re.search(r"\b(?:offset|cursor|page|next_page|scroll_id)\b", content, re.I))
                if not (has_loop and has_pagination_token):
                    issues.append(
                        f"{script_path.name}: hardcoded API limit={val} detected without pagination loop (offset/cursor/page exhaustion). "
                        "Must implement complete multi-page traversal to retrieve full cohort."
                    )
                    break

    return issues


def count_file_physical_rows(file_path: Path) -> int | None:
    """Accurately count physical rows in standard tabular formats (CSV, TSV, JSONL)."""
    suffix = file_path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        try:
            line_count = 0
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for _ in f:
                    line_count += 1
            # Subtract 1 for header row if > 0
            return max(0, line_count - 1)
        except Exception:
            return None
    elif suffix == ".jsonl":
        try:
            count = 0
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.strip():
                        count += 1
            return count
        except Exception:
            return None
    elif suffix == ".json":
        try:
            data = json.loads(file_path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict):
                # Check for records or data key
                for k in ("records", "data", "items", "results"):
                    if isinstance(data.get(k), list):
                        return len(data[k])
        except Exception:
            return None
    return None


@check("data_acquisition_integrity")
def data_acquisition_integrity(ctx: Ctx) -> Result:
    """Audit all data acquisition and cleaning scripts to guarantee zero arbitrary truncation."""
    scripts_to_check: list[Path] = []
    
    # 1. Check scripts in 02_data/ and 03_analysis/code/
    for folder in ("02_data", "03_analysis/code"):
        p = ctx.p(folder)
        if p.exists():
            for ext in ("*.py", "*.R", "*.sh"):
                scripts_to_check.extend(p.rglob(ext))

    # Also check project root for standalone acquisition scripts
    for p in ctx.project.glob("*.py"):
        if p.is_file() and p.name not in ("test_", "conftest.py"):
            scripts_to_check.append(p)

    scripts_to_check = sorted(set(scripts_to_check))
    violations: list[str] = []

    for s in scripts_to_check:
        # Skip temporary test scripts or venv
        rel_s = s.relative_to(ctx.project).as_posix()
        if rel_s.startswith("temp/") or "/temp/" in rel_s or ".venv/" in rel_s:
            continue
        hits = scan_code_for_truncation(s)
        violations.extend(hits)

    if violations:
        return Result(
            False,
            "data_acquisition_integrity",
            f"FATAL INTEGRITY VIOLATION: {len(violations)} rogue truncation/sampling pattern(s) detected in data code:\n"
            + "\n".join(f"  - {v}" for v in violations[:10]),
            [
                "Never use nrows=, head(N), arbitrary sampling, or fake loop breaks to shortcut data acquisition.",
                "Public datasets and APIs must be ingested in full (Full Census) with complete pagination exhaustion.",
                "If sampling is scientifically justified by protocol, specify APPROVED_SAMPLING in 02_data/data_census.json with IRB/power documentation."
            ]
        )

    return Result(
        True,
        "data_acquisition_integrity",
        f"Verified {len(scripts_to_check)} script(s): zero arbitrary truncation or unapproved sampling detected"
    )


@check("data_census_match")
def data_census_match(ctx: Ctx) -> Result:
    """Enforce physical census accounting between acquisition plan, raw files, and dataset summary."""
    census_file = ctx.p("02_data/data_census.json")
    summary_file = ctx.p("03_analysis/results/dataset_summary.json")
    plan_file = ctx.p("02_data/acquisition_plan.md")

    if not census_file.exists():
        return Result(
            False,
            "data_census_match",
            "Missing '02_data/data_census.json'. Data acquisition must output an auditable census manifest.",
            ["Create 02_data/data_census.json documenting strategy, actual_raw_rows, and exhaustion_verified."]
        )

    try:
        census_data = json.loads(census_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return Result(False, "data_census_match", f"02_data/data_census.json invalid JSON: {exc}")

    required_keys = ["strategy", "actual_raw_rows", "exhaustion_verified", "retrieval_method"]
    missing_keys = [k for k in required_keys if k not in census_data]
    if missing_keys:
        return Result(
            False,
            "data_census_match",
            f"02_data/data_census.json missing required audit fields: {', '.join(missing_keys)}"
        )

    strategy = census_data.get("strategy")
    if strategy not in ("FULL_CENSUS", "APPROVED_SAMPLING"):
        return Result(
            False,
            "data_census_match",
            f"Invalid strategy '{strategy}'. Must be 'FULL_CENSUS' or 'APPROVED_SAMPLING'."
        )

    if strategy == "FULL_CENSUS" and not census_data.get("exhaustion_verified", False):
        return Result(
            False,
            "data_census_match",
            "Full Census requires exhaustion_verified: true (proof of complete pagination / complete download)."
        )

    census_rows = census_data.get("actual_raw_rows", 0)
    if not isinstance(census_rows, int) or census_rows <= 0:
        return Result(
            False,
            "data_census_match",
            f"actual_raw_rows must be a positive integer, got: {census_rows}"
        )

    # 1. Reconcile with 03_analysis/results/dataset_summary.json
    if summary_file.exists():
        try:
            summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
            summary_rows = summary_data.get("n_rows")
            if summary_rows is not None and summary_rows != census_rows:
                return Result(
                    False,
                    "data_census_match",
                    f"FATAL RECONCILIATION MISMATCH: data_census.json declares {census_rows} raw rows, "
                    f"but dataset_summary.json reports {summary_rows} rows. Did someone sneakily truncate the analysis set?"
                )
        except Exception as exc:
            return Result(False, "data_census_match", f"dataset_summary.json unreadable: {exc}")

    # 2. Reconcile with expected volume in acquisition_plan.md if declared
    if plan_file.exists():
        plan_text = plan_file.read_text(encoding="utf-8", errors="replace")
        # Look for explicit Expected volume/shape numbers (e.g., "Expected shape: 15,000 rows" or "N = 12000")
        m_exp = re.search(r"(?i)\b(?:expected\s+(?:volume|shape|n|rows?|sample\s*size))\s*[:=~]\s*([><~]?\s*[\d,]+)", plan_text)
        if m_exp:
            exp_str = re.sub(r"[^\d]", "", m_exp.group(1))
            if exp_str:
                expected_val = int(exp_str)
                # If actual is less than 50% of expected and it's FULL_CENSUS, flag severe discrepancy
                if strategy == "FULL_CENSUS" and census_rows < expected_val * 0.5:
                    return Result(
                        False,
                        "data_census_match",
                        f"SUSPICIOUS DATA TRUNCATION: acquisition_plan.md anticipated ~{expected_val} records, "
                        f"but only {census_rows} were acquired. If true population is smaller, update acquisition_plan.md with justification."
                    )

    # 3. Physical Disk Reality Check
    raw_files = [p for p in (ctx.project / "02_data" / "raw").rglob("*") if p.is_file() and p.name != ".gitkeep"]
    if not raw_files:
        return Result(False, "data_census_match", "02_data/raw/ contains no physical raw files.")

    # Check physical row counts for tabular files
    for rf in raw_files:
        phys_rows = count_file_physical_rows(rf)
        if phys_rows is not None:
            # If physical file has significantly fewer rows than declared census (e.g. file only has 100 lines but census says 10000)
            if phys_rows < census_rows * 0.9:
                return Result(
                    False,
                    "data_census_match",
                    f"PHYSICAL DATA AUDIT FAILURE: Physical file '{rf.name}' only contains {phys_rows} rows on disk, "
                    f"but data_census.json claims {census_rows} rows! Data has been falsified or truncated on disk."
                )

    return Result(
        True,
        "data_census_match",
        f"Data census verified: {census_rows} records ({strategy}), complete exhaustion confirmed, disk files match"
    )
