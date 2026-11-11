#!/usr/bin/env python3
"""Render an independent aggregate review SVG; never executes Tableau.

Added November 2026. Uses the public attributed CSV and the existing audit's
raw-record definitions. Original Tableau screenshots and source stay unchanged.
"""
from __future__ import annotations

import argparse
from html import escape
import math
from pathlib import Path

try:
    from scripts.analyze_salaries import analyze_csv
except ImportError:
    from analyze_salaries import analyze_csv


def quantity(value: object, *, count: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Review metrics must be finite and nonnegative")
    if count and int(value) != value:
        raise ValueError("Review counts must be integers")
    return value


def text(x: int, y: int, value: object, size: int = 18, color: str = "#24364b", weight: int = 400) -> str:
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(str(value))}</text>'


def render(summary: dict) -> str:
    """Create a deterministic image from reviewed aggregate fields only."""
    try:
        rows = quantity(summary["row_count"], count=True)
        mean = quantity(summary["salary_validity"]["salary_in_usd"]["mean"])
        residences = quantity(summary["country_scope"]["employee_residence"]["distinct_country_code_count"], count=True)
        years = sorted(summary["year_counts"])
        if not years or any(len(y) != 4 or not y.isdigit() for y in years):
            raise ValueError("Expected calendar work years")
        year_label = years[0] if years[0] == years[-1] else f"{years[0]}–{years[-1]}"
        groups = []
        for key in ["experience_groups", "remote_ratio_groups"]:
            panel = []
            for g in summary[key]:
                count = quantity(g["valid_positive_usd_count"], count=True)
                value = g["mean_salary_usd"]
                if count == 0 and value is None:
                    panel.append((str(g["group"]), count, None))
                else:
                    if count == 0:
                        raise ValueError("A mean needs a nonzero denominator")
                    panel.append((str(g["group"]), count, quantity(value)))
            if not panel or len(panel) > 6:
                raise ValueError("Review panel needs one to six groups")
            groups.append(panel)
        for count in summary["year_counts"].values():
            quantity(count, count=True)
    except (KeyError, TypeError) as exc:
        raise ValueError("Missing review aggregate contract") from exc

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="900" viewBox="0 0 1080 900" role="img" aria-labelledby="title description">',
           '<title id="title">Historical salary snapshot — independent review view</title>',
           '<desc id="description">Reproducible raw-record salary aggregates with group counts. New Python SVG, not a Tableau export.</desc>',
           '<rect width="1080" height="900" fill="#f4f7fb"/>',
           '<g font-family="Arial, Helvetica, sans-serif">',
           text(40, 50, "SALARY SNAPSHOT / REVIEW VIEW", 14, "#087f8c", 700),
           text(40, 91, "Data & AI workforce", 34, weight=700),
           text(40, 123, f"{year_label} submitted records · November 2026 independent audit", 18),
           text(40, 151, "New Python SVG, not a Tableau export. Original dashboard preserved below.", 16)]
    for x, label, value in [(40, "RECORDS", f"{rows:,}"), (390, "MEAN SALARY / USD", f"${mean:,.2f}"), (740, "EMPLOYEE RESIDENCE CODES", str(residences))]:
        out.extend([f'<rect x="{x}" y="181" width="300" height="102" rx="10" fill="white"/>', text(x + 20, 211, label, 13, "#5d6c7e", 700), text(x + 20, 255, value, 30, weight=700)])
    labels = {"EN": "Entry-level", "MI": "Mid-level", "SE": "Senior", "EX": "Executive", "0": "On-site", "50": "Hybrid", "100": "Remote"}
    maximum = max((v for panel in groups for _, _, v in panel if v is not None), default=1) or 1
    for x, title, panel in [(40, "Mean salary by experience", groups[0]), (560, "Mean salary by work arrangement", groups[1])]:
        out.append(text(x, 333, title, 22, weight=700))
        for index, (label, count, value) in enumerate(panel):
            y = 375 + index * 72
            out.extend([text(x, y, labels.get(label, label), 17, weight=700), text(x, y + 24, f"n={count:,}", 14, "#5d6c7e")])
            width = 200 * (value or 0) / maximum
            out.append(f'<rect x="{x + 155}" y="{y - 14}" width="{width:.3f}" height="25" rx="3" fill="#087f8c"/>')
            out.append(text(x + 155, y + 38, "No eligible salary" if value is None else f"${value:,.0f}", 16))
    counts = " · ".join(f"{y}: {summary['year_counts'][y]:,}" for y in years)
    out.extend([text(40, 795, "Sample composition by work year", 19, weight=700), text(40, 823, counts, 18),
                text(40, 855, "Anonymous convenience sample; repeated rows retained. Group means are descriptive.", 15),
                text(40, 879, "Different yearly composition is not like-for-like wage growth. Geography means employee residence.", 14), '</g></svg>'])
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.source_csv.resolve() == args.output.resolve():
        parser.error("Output must differ from source CSV")
    try:
        svg = render(analyze_csv(args.source_csv))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(svg, encoding="utf-8")
    except (ValueError, OSError, UnicodeError) as exc:
        parser.exit(1, f"Review render failed: {exc}\n")
    print("Wrote independent aggregate review SVG; input unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
