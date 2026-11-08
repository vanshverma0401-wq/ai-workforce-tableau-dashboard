#!/usr/bin/env python3
"""New November 2026 portfolio audit utility, not original Tableau project code.

Read a salary CSV and emit only structure, validity checks and grouped aggregates.
No input rows are removed or modified. No Tableau calculations are executed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
from typing import Iterable

FIELDS = (
    "work_year", "experience_level", "employment_type", "job_title", "salary",
    "salary_currency", "salary_in_usd", "employee_residence", "remote_ratio",
    "company_location", "company_size",
)
ENUMS = {
    "experience_level": {"EN", "MI", "SE", "EX"},
    "employment_type": {"FT", "PT", "CT", "FL"},
    "company_size": {"S", "M", "L"},
    "remote_ratio": {"0", "50", "100"},
}


def positive_number(value: object) -> float | None:
    """Accept finite, positive numeric CSV text; zero remains an invalid salary."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def mean(values: list[float]) -> float | None:
    return round(math.fsum(values) / len(values), 6) if values else None


def grouped(rows: list[dict[str, str]], key: str) -> list[dict]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    result = []
    for label, members in sorted(groups.items()):
        values = [v for row in members if (v := positive_number(row["salary_in_usd"])) is not None]
        result.append({"group": label, "row_count": len(members),
                       "valid_positive_usd_count": len(values), "mean_salary_usd": mean(values)})
    return result


def analyze_rows(headers: list[str], rows: Iterable[dict[str, str]]) -> dict:
    if len(headers) != len(set(headers)):
        raise ValueError("Duplicate column names are not supported")
    missing = set(FIELDS) - set(headers)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    records = list(rows)
    for row in records:
        if None in row or any(row.get(key) is None for key in headers):
            raise ValueError("Row width does not match the CSV header")
    duplicates = len(records) - len({tuple(row[key] for key in headers) for row in records})
    years: Counter[str] = Counter()
    invalid_years = 0
    for row in records:
        year = row["work_year"]
        if re.fullmatch(r"\d{4}", year) and 1900 <= int(year) <= 2200:
            years[year] += 1
        else:
            invalid_years += 1
    enum_checks = {}
    for key, allowed in ENUMS.items():
        observed = Counter(row[key] for row in records)
        enum_checks[key] = {"allowed": sorted(allowed),
                            "invalid_row_count": sum(count for value, count in observed.items() if value not in allowed),
                            "invalid_values": dict(sorted((value, count) for value, count in observed.items() if value not in allowed))}
    salary_checks = {}
    for key in ("salary", "salary_in_usd"):
        valid = [number for row in records if (number := positive_number(row[key])) is not None]
        salary_checks[key] = {"valid_positive_count": len(valid),
                              "invalid_or_nonpositive_count": len(records) - len(valid)}
        if key == "salary_in_usd":
            salary_checks[key]["mean"] = mean(valid)
            salary_checks[key]["at_least_200000_count"] = sum(v >= 200000 for v in valid)
            salary_checks[key]["greater_than_200000_count"] = sum(v > 200000 for v in valid)
            salary_checks[key]["exactly_200000_count"] = sum(v == 200000 for v in valid)
    titles = grouped(records, "job_title")
    titles.sort(key=lambda group: (group["mean_salary_usd"] is None,
                                   -(group["mean_salary_usd"] or 0), group["group"]))
    country_checks = {}
    for key in ("employee_residence", "company_location"):
        observed = {row[key] for row in records}
        country_checks[key] = {
            "distinct_country_code_count": len(observed - {""}),
            "missing_row_count": sum(not row[key] for row in records),
            "non_two_letter_code_row_count": sum(not re.fullmatch(r"[A-Z]{2}", row[key]) for row in records),
            "code_check_scope": "Two-letter format only; country-code membership is not validated.",
        }
    return {
        "row_count": len(records), "field_count": len(headers), "fields": headers,
        "distinct_row_count": len(records) - duplicates,
        "duplicate_row_occurrences": duplicates,
        "year_counts": dict(sorted(years.items())), "invalid_year_row_count": invalid_years,
        "enum_validity": enum_checks, "salary_validity": salary_checks,
        "country_scope": country_checks,
        "experience_groups": grouped(records, "experience_level"),
        "company_size_groups": grouped(records, "company_size"),
        "remote_ratio_groups": grouped(records, "remote_ratio"),
        "title_groups_by_mean_salary_usd": titles,
    }


def analyze_csv(path: Path) -> dict:
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing")
    result = analyze_rows(reader.fieldnames, reader)
    return {
        "schema_version": 1, "tooling_introduced": "2026-11-08",
        "tooling_scope": "New portfolio data-audit code; not the original 2025 Tableau Prep or workbook calculations.",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "method": {
            "input_modified": False, "row_level_records_emitted": False,
            "duplicate_policy": "Retain every row; count exact duplicate occurrences without deduplication.",
            "salary_policy": "Means use finite positive salary_in_usd values; raw salary in mixed currencies is not averaged.",
            "group_count_policy": "row_count retains all group rows; valid_positive_usd_count is the mean denominator.",
            "enum_policy": "Report invalid values without dropping their rows or silently relabeling them.",
            "population_claim": "None. Descriptive snapshot aggregates do not establish representative labor-market estimates.",
            "tableau_runtime_executed": False,
        },
        **result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.source_csv.resolve() == args.output.resolve():
        parser.error("Output must differ from the source CSV")
    try:
        result = analyze_csv(args.source_csv)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, f"Data audit failed: {exc}\n")
    print(f"Audited {result['row_count']} rows; input left unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
