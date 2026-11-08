"""Synthetic fixture checks for new November 2026 source-audit tooling."""
from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("extract_tableau_evidence", ROOT / "scripts/extract_tableau_evidence.py")
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a2ioAAAAASUVORK5CYII=")
GUID = "12345678-1234-1234-1234-123456789abc"


def fixtures(root: Path, *, private_xml: bool = False) -> tuple[Path, Path, bytes]:
    xml = f'''<workbook version="18.1"><datasources><datasource><column name="[Salary (USD) (bin)]"><calculation class="bin" formula="[Salary (USD)]" size="20000" /></column></datasource></datasources>
    <worksheets><worksheet name="Example"><table><view><column-instance column="[Salary (USD)]" derivation="Avg" name="[avg:Salary (USD):qk]"/><filter class="categorical" column="[federated.{GUID}].[Employee Country]"/></view><rows>[federated.{GUID}].[Employee Country]</rows><cols>[federated.{GUID}].[avg:Salary (USD):qk]</cols></table></worksheet><worksheet name="Not placed"/></worksheets>
    <dashboards><dashboard name="Dashboard"><zones><zone name="Example"/><zone name="Example"/><zone type-v2="filter" param="[federated.{GUID}].[Employee Country]"/></zones></dashboard></dashboards>
    <actions><action caption="Filter"><activation type="on-select"/><source worksheet="Example"/></action></actions>
    <thumbnails><thumbnail name="Example" width="1" height="1">{base64.b64encode(PNG).decode()}</thumbnail></thumbnails>
    {"<connection dbname='/Users/synthetic/private.hyper' />" if private_xml else ""}</workbook>'''.encode()
    flow = {"documentId": GUID, "connections": {"private": {"filename": "/Users/synthetic/source.csv"}}, "nodes": {
        "input": {"nodeType": ".v1.LoadCsv", "actions": [{"nodeType": ".v1.RenameColumn", "columnName": "salary_in_usd", "rename": "Salary (USD)"}]},
        "container": {"nodeType": ".v1.Container", "loomContainer": {"initialNodes": ["a"], "nodes": {
            "a": {"nodeType": ".v1.AddColumn", "columnName": "High paying", "expression": 'IF [Salary (USD)] >= 200000 THEN "Yes" ELSE "No" END', "nextNodes": [{"nextNodeId": "b"}]},
            "b": {"nodeType": ".v1.Remap", "columnName": "Title", "values": {'"Engineer"': ['"Engineer"', '"Engineering"']}, "nextNodes": []}}}}}}
    twbx, tfl = root / "example.twbx", root / "example.tfl"
    with ZipFile(twbx, "w") as z:
        z.writestr("example.twb", xml)
        z.writestr("Data/private.hyper", b"DO_NOT_OPEN")
    with ZipFile(tfl, "w") as z:
        z.writestr("flow", json.dumps(flow))
        z.writestr("metadata", "DO_NOT_PUBLISH")
    return twbx, tfl, xml


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_source_bytes_preserved_and_only_selected_outputs_written(self):
        twbx, tfl, xml = fixtures(self.root)
        before = (twbx.read_bytes(), tfl.read_bytes())
        out = self.root / "public"
        result = exporter.export_evidence(twbx, tfl, out)
        self.assertEqual((result["worksheet_count"], result["dashboard_count"]), (2, 1))
        self.assertEqual(result["dashboards"][0]["placed_worksheet_count"], 1)
        self.assertEqual((out / "tableau/original_workbook.twb").read_bytes(), xml)
        self.assertEqual((twbx.read_bytes(), tfl.read_bytes()), before)
        self.assertFalse(list(out.rglob("*.hyper")))
        self.assertFalse(list(out.rglob("*.tfl")))
        self.assertEqual((out / "assets/worksheets/example.png").read_bytes(), PNG)

    def test_formulas_remaps_and_calculated_bins_are_inspectable(self):
        twbx, tfl, _ = fixtures(self.root)
        out = self.root / "public"
        result = exporter.export_evidence(twbx, tfl, out)
        prep = json.loads((out / "prep/transformations.json").read_text())
        self.assertEqual(prep["renames"], [{"source": "salary_in_usd", "target": "Salary (USD)"}])
        self.assertIn(">= 200000", prep["cleaning_steps_in_order"][0]["expression"])
        self.assertEqual(prep["cleaning_steps_in_order"][1]["mappings"], [{"target": "Engineer", "sources": ["Engineer", "Engineering"]}])
        self.assertEqual(result["workbook_calculations"][0]["size"], "20000")

    def test_json_omits_private_connections_ids_metadata_and_hyper_contents(self):
        twbx, tfl, _ = fixtures(self.root)
        out = self.root / "public"
        exporter.export_evidence(twbx, tfl, out)
        for path in out.rglob("*.json"):
            text = path.read_text()
            for value in [GUID, "/Users/synthetic", str(self.root), "DO_NOT_OPEN", "DO_NOT_PUBLISH"]:
                self.assertNotIn(value, text)
        result = json.loads((out / "technical/workbook_inventory.json").read_text())
        self.assertEqual(result["worksheets"][0]["rows"], ["[Employee Country]"])
        self.assertEqual(result["dashboards"][0]["visible_filter_fields"], ["[Employee Country]"])

    def test_private_xml_rejected_before_any_output_is_written(self):
        twbx, tfl, _ = fixtures(self.root, private_xml=True)
        out = self.root / "public"
        with self.assertRaisesRegex(exporter.EvidenceError, "Private path"):
            exporter.export_evidence(twbx, tfl, out)
        self.assertFalse(out.exists())

    def test_malformed_workbook_and_entity_documents_are_rejected(self):
        for value in [b"<workbook", b"<!DOCTYPE workbook><workbook/>", b"<not-workbook/>"]:
            with self.assertRaises(exporter.EvidenceError):
                exporter.workbook_definition(value)

    def test_bounded_selected_member_and_ambiguous_member_rejected(self):
        twbx, tfl, _ = fixtures(self.root)
        with patch.object(exporter, "MAX_MEMBER_BYTES", 10):
            with self.assertRaises(exporter.EvidenceError):
                exporter.export_evidence(twbx, tfl, self.root / "public")
        with ZipFile(twbx, "a") as z:
            z.writestr("second.twb", b"<workbook/>")
        with self.assertRaisesRegex(exporter.EvidenceError, "exactly one"):
            exporter.export_evidence(twbx, tfl, self.root / "public")

    def test_cycles_are_rejected_without_executing_expressions(self):
        flow = {"nodes": {"container": {"nodeType": ".v1.Container", "loomContainer": {
            "initialNodes": ["a"], "nodes": {"a": {"nodeType": ".v1.AddColumn", "columnName": "A", "expression": "DO_NOT_EXECUTE()", "nextNodes": [{"nextNodeId": "a"}]}}}}}}
        with self.assertRaisesRegex(exporter.EvidenceError, "cyclic"):
            exporter.prep_evidence(flow)


if __name__ == "__main__":
    unittest.main()
