#!/usr/bin/env python3
"""Static Tableau evidence export added for the November 2026 portfolio review.

Reads selected ZIP/XML/JSON members only. It does not execute Tableau, evaluate
calculations, open Hyper databases, refresh sources or produce a runnable build.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_THUMBNAILS = 50
SENSITIVE = re.compile(r"/(?:Users|home|Volumes)/|[A-Za-z]:\\|\\\\|"
                       r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", re.I)
IDENTIFIER = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b", re.I)
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
FILENAMES = {
    "AI Salaries Dashboard: Exploring Pay by Role, Experience, and Work Style": "dashboard-saved-thumbnail.png",
    "Bar Chart - Job Title Salaries": "job-title-salaries.png",
    "Bar Chart - Salary by Job Title": "salary-distribution.png",
    "Bar Chart - Salary by Remote Ratio": "experience-remote-distribution.png",
    "Box Plot - Salary by Experience Level": "salary-by-company-size.png",
    "KPI – Average Salary": "kpi-average-salary.png",
    "KPI – Countries": "kpi-countries.png",
    "KPI – Job Records": "kpi-records.png",
    "Line - Salary Trend Over Time": "salary-trend.png",
    "Map - Salary by Company Location": "salary-by-employee-country.png",
    "Pie Chart - Remote vs On-Site Work": "remote-work-distribution.png",
}


class EvidenceError(ValueError):
    """Malformed, excessive or unsafe selected source content."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe(value: object) -> str:
    if not isinstance(value, str):
        return ""
    if SENSITIVE.search(value) or IDENTIFIER.search(value) or "http://" in value or "https://" in value:
        return "[redacted]"
    return "".join(c for c in value if c.isprintable())[:5000]


def field(value: object) -> str:
    if not isinstance(value, str):
        return ""
    # Remove workbook-local datasource IDs, retaining the actual field token.
    return safe(re.sub(r"\[(?:federated|hyper)\.[^\]]+\]\.", "", value))


def read_selected(path: Path, selector) -> tuple[str, bytes]:
    try:
        with ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ENTRIES:
                raise EvidenceError("Archive exceeds the entry-count limit")
            chosen = [i for i in members if selector(i.filename)]
            if len(chosen) != 1:
                raise EvidenceError("Expected exactly one selected archive member")
            info = chosen[0]
            if info.file_size > MAX_MEMBER_BYTES:
                raise EvidenceError("Selected member exceeds the size limit")
            with archive.open(info) as stream:
                raw = stream.read(MAX_MEMBER_BYTES + 1)
            if len(raw) > MAX_MEMBER_BYTES:
                raise EvidenceError("Selected member exceeds the size limit")
            return info.filename, raw
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise EvidenceError("Cannot read selected ZIP member") from exc


def workbook_definition(raw: bytes) -> ET.Element:
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise EvidenceError("DTD/entity declarations are not accepted")
    try:
        text = raw.decode("utf-8-sig")
        root = ET.fromstring(raw)
    except (UnicodeError, ET.ParseError) as exc:
        raise EvidenceError("Invalid UTF-8 workbook XML") from exc
    if root.tag != "workbook":
        raise EvidenceError("Expected a workbook XML root")
    if SENSITIVE.search(text):
        raise EvidenceError("Private path or contact pattern in workbook definition")
    urls = re.findall(r"https?://[^\s'\"<>]+", text)
    if any(url != "http://www.tableausoftware.com/xml/user" for url in urls):
        raise EvidenceError("Unexpected URL in workbook definition")
    for node in root.iter():
        for key, value in node.attrib.items():
            if key.lower() in {"password", "token", "secret"} and value:
                raise EvidenceError("Credential-like attribute in workbook definition")
            if key.lower() == "username" and value not in {"", "tableau_internal_user"}:
                raise EvidenceError("Unexpected username in workbook definition")
    return root


def prep_evidence(flow: dict) -> dict:
    nodes = flow.get("nodes", {})
    if not isinstance(nodes, dict):
        raise EvidenceError("Prep nodes must be an object")
    renames = []
    transforms = []
    for node in nodes.values():
        for action in node.get("actions", []):
            if action.get("nodeType") == ".v1.RenameColumn":
                renames.append({"source": safe(action.get("columnName")), "target": safe(action.get("rename"))})
        if node.get("nodeType") != ".v1.Container":
            continue
        inner = node.get("loomContainer", {})
        inner_nodes = inner.get("nodes", {})
        current_nodes = inner.get("initialNodes", [])
        if len(current_nodes) != 1:
            raise EvidenceError("Expected one cleaning-chain start")
        current = current_nodes[0]
        seen = set()
        while current:
            if current in seen or current not in inner_nodes:
                raise EvidenceError("Invalid or cyclic cleaning chain")
            seen.add(current)
            step = inner_nodes[current]
            record = {"order": len(transforms) + 1, "type": safe(step.get("nodeType")),
                      "field": safe(step.get("columnName"))}
            if step.get("nodeType") == ".v1.AddColumn":
                # Preserve formula line breaks while screening sensitive strings.
                expression = step.get("expression", "")
                record["expression"] = expression if safe(expression) != "[redacted]" else "[redacted]"
            elif step.get("nodeType", "").endswith("RichNullFilter"):
                record["stored_filter_code"] = step.get("filter")
            elif step.get("nodeType") == ".v1.Remap":
                mappings = []
                for new, old_values in step.get("values", {}).items():
                    try:
                        target = json.loads(new)
                        sources = [json.loads(v) for v in old_values]
                    except (TypeError, ValueError) as exc:
                        raise EvidenceError("Invalid stored remap labels") from exc
                    mappings.append({"target": safe(target), "sources": [safe(v) for v in sources]})
                record["mappings"] = mappings
            transforms.append(record)
            next_nodes = step.get("nextNodes", [])
            if len(next_nodes) > 1:
                raise EvidenceError("This exporter expects a single cleaning chain")
            current = next_nodes[0]["nextNodeId"] if next_nodes else None
    return {"original_project_year": 2025, "export_tool_added": "2026-11-08",
            "scope": "Selected saved Prep definitions; paths, IDs and personal metadata omitted. Not an executed or runnable flow.",
            "renames": renames, "cleaning_steps_in_order": transforms,
            "not_observed_in_selected_chain": [label for term, label in
                [("duplic", "deduplication node"), ("outlier", "outlier-removal node")]
                if not any(term in s["type"].lower() for s in transforms)],
            "runtime_validated": False}


def workbook_inventory(root: ET.Element, twb_raw: bytes, package_raw: bytes, flow_raw: bytes) -> dict:
    sheets = []
    for sheet in root.findall("./worksheets/worksheet"):
        instances = []
        for column in sheet.findall(".//column-instance"):
            if "__tableau_internal_object_id__" in column.get("column", ""):
                continue
            instances.append({"field": field(column.get("column")), "derivation": safe(column.get("derivation")),
                              "token": field(column.get("name"))})
        sheets.append({"name": safe(sheet.get("name")),
                       "title": safe(" ".join(t.text or "" for t in sheet.findall(".//title//run"))),
                       "rows": [field(t.text) for t in sheet.findall(".//rows")],
                       "columns": [field(t.text) for t in sheet.findall(".//cols")],
                       "field_instances": instances,
                       "filters": [{"class": safe(t.get("class")), "field": field(t.get("column"))}
                                   for t in sheet.findall(".//filter")],
                       "mark_types": sorted({safe(t.get("class")) for t in sheet.findall(".//mark")})})
    dashboards = []
    for dashboard in root.findall("./dashboards/dashboard"):
        placed = sorted({safe(z.get("name")) for z in dashboard.findall("./zones//zone")
                         if z.get("name") and not z.get("type-v2")})
        controls = sorted({field(z.get("param")) for z in dashboard.findall(".//zone")
                           if z.get("type-v2") == "filter"})
        dashboards.append({"name": safe(dashboard.get("name")), "placed_worksheet_count": len(placed),
                           "placed_worksheets": placed, "visible_filter_fields": controls})
    actions = []
    for action in root.findall("./actions/action"):
        source, activation = action.find("source"), action.find("activation")
        actions.append({"caption": safe(action.get("caption")),
                        "activation": safe(activation.get("type")) if activation is not None else "",
                        "source_worksheet": safe(source.get("worksheet")) if source is not None else ""})
    bins, source_fields = [], []
    for column in root.findall("./datasources/datasource/column"):
        if "__tableau_internal_object_id__" not in column.get("name", ""):
            source_fields.append({"field": field(column.get("name")), "datatype": safe(column.get("datatype")),
                                  "role": safe(column.get("role")), "semantic_role": safe(column.get("semantic-role"))})
        calc = column.find("calculation")
        if calc is not None:
            bins.append({"field": field(column.get("name")), "class": safe(calc.get("class")),
                         "formula": field(calc.get("formula")), "size": safe(calc.get("size"))})
    return {"inventory_format": 1, "original_project_year": 2025, "export_tool_added": "2026-11-08",
            "source_sha256": {"twbx": digest(package_raw), "final_twb": digest(twb_raw), "prep_flow_zip": digest(flow_raw)},
            "scope": {"static_only": True, "hyper_opened": False, "tableau_executed": False,
                      "private_paths_and_ids_in_json": False,
                      "not_established": ["fresh rendering", "refresh", "flow execution", "published workbook runtime"]},
            "worksheet_count": len(sheets), "dashboard_count": len(dashboards),
            "source_fields": source_fields,
            "worksheets": sheets, "dashboards": dashboards, "dashboard_actions": actions,
            "workbook_calculations": bins}


def export_evidence(twbx: Path, tfl: Path, output: Path) -> dict:
    _, twb_raw = read_selected(twbx, lambda n: n.endswith(".twb"))
    _, prep_raw = read_selected(tfl, lambda n: n == "flow")
    root = workbook_definition(twb_raw)
    try:
        flow = json.loads(prep_raw)
    except (UnicodeError, ValueError) as exc:
        raise EvidenceError("Invalid Prep flow JSON") from exc
    if not isinstance(flow, dict):
        raise EvidenceError("Prep flow must be a JSON object")
    prep = prep_evidence(flow)
    inventory = workbook_inventory(root, twb_raw, twbx.read_bytes(), tfl.read_bytes())
    payloads = {"tableau/original_workbook.twb": twb_raw,
                "prep/transformations.json": (json.dumps(prep, indent=2) + "\n").encode(),
                "technical/workbook_inventory.json": (json.dumps(inventory, indent=2) + "\n").encode()}
    formulas = [s for s in prep["cleaning_steps_in_order"] if "expression" in s]
    text = "Saved Tableau Prep calculations from the 2025 team project\nExported for the November 2026 source review; not executed by this tool.\n\n"
    text += "\n\n".join(s["field"] + "\n" + s["expression"] for s in formulas) + "\n"
    payloads["prep/calculated_fields.txt"] = text.encode()
    figures = []
    thumbnails = root.findall("./thumbnails/thumbnail")
    if len(thumbnails) > MAX_THUMBNAILS:
        raise EvidenceError("Too many saved thumbnails")
    used = set()
    for thumb in thumbnails:
        name = safe(thumb.get("name"))
        filename = FILENAMES.get(name) or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] + ".png"
        relative = "assets/worksheets/" + filename
        if relative in used:
            raise EvidenceError("Duplicate thumbnail output")
        used.add(relative)
        try:
            png = base64.b64decode("".join((thumb.text or "").split()), validate=True)
        except ValueError as exc:
            raise EvidenceError("Invalid thumbnail base64") from exc
        if not png.startswith(PNG_HEADER):
            raise EvidenceError("Saved thumbnail is not a PNG")
        payloads[relative] = png
        figures.append({"source_name": name, "asset": relative,
                        "source_width": int(thumb.get("width", "0")), "source_height": int(thumb.get("height", "0")),
                        "sha256": digest(png), "source_kind": "saved workbook thumbnail",
                        "fresh_runtime_export": False})
    manifest = {"original_project_year": 2025, "source_twb_sha256": digest(twb_raw),
                "export_tool_added": "2026-11-08", "figure_count": len(figures),
                "note": "Saved source thumbnails, including one dashboard. Several crop the viewport, labels or plot area, and some text is small. These are not fresh runtime renders.",
                "figures": figures}
    payloads["technical/figure_manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    sources = {twbx.resolve(), tfl.resolve()}
    if any((output / relative).resolve() in sources for relative in payloads):
        raise EvidenceError("Output would overwrite a source archive")
    for relative, raw in payloads.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("twbx", type=Path)
    parser.add_argument("tfl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = export_evidence(args.twbx, args.tfl, args.output_dir)
    except (EvidenceError, OSError) as exc:
        parser.exit(1, f"Evidence export failed: {exc}\n")
    print(f"Exported {result['worksheet_count']} worksheet definitions and {result['dashboard_count']} dashboard definitions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
