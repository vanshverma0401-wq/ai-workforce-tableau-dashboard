"""Contract checks for the separately labeled, reproducible review visual."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "render_review.py"


class ReviewVisualTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), "Missing review renderer")
        spec = importlib.util.spec_from_file_location("render_review", SCRIPT)
        self.renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.renderer)
        self.summary = json.loads((ROOT / "technical/data_validation.json").read_text())

    def test_real_public_aggregates_have_correct_labels_and_explicit_scope(self):
        svg = self.renderer.render(self.summary)
        ET.fromstring(svg)
        self.assertIn("637", svg)
        self.assertIn("113,275.44", svg)
        self.assertIn("employee residence", svg)
        self.assertIn("not a Tableau export", svg)
        self.assertIn("2020–2022", svg)
        self.assertIn("repeated rows retained", svg)

    def test_output_is_deterministic_and_escapes_group_labels(self):
        self.summary["experience_groups"][0]["group"] = "Example & <group>"
        first = self.renderer.render(self.summary)
        self.assertEqual(first, self.renderer.render(self.summary))
        self.assertIn("Example &amp; &lt;group&gt;", first)
        ET.fromstring(first)

    def test_nonfinite_means_and_negative_denominators_are_rejected(self):
        for value in [float("nan"), float("inf"), -1]:
            with self.subTest(value=value):
                self.summary["experience_groups"][0]["mean_salary_usd"] = value
                with self.assertRaises(ValueError):
                    self.renderer.render(self.summary)
        self.summary["experience_groups"][0]["mean_salary_usd"] = 100
        self.summary["experience_groups"][0]["valid_positive_usd_count"] = -1
        with self.assertRaises(ValueError):
            self.renderer.render(self.summary)

    def test_cli_reads_public_csv_without_modifying_it(self):
        source = ROOT / "data/salaries-ai-jobs-net.csv"
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "overview.svg"
            self.assertEqual(self.renderer.main([str(source), "--output", str(output)]), 0)
            self.assertEqual(before, source.read_bytes())
            self.assertNotIn(str(source), output.read_text())
            ET.fromstring(output.read_text())

    def test_cli_refuses_to_overwrite_input(self):
        source = ROOT / "data/salaries-ai-jobs-net.csv"
        before = source.read_bytes()
        with self.assertRaises(SystemExit):
            self.renderer.main([str(source), "--output", str(source)])
        self.assertEqual(source.read_bytes(), before)

    def test_empty_comparison_panel_is_rejected(self):
        self.summary["experience_groups"] = []
        with self.assertRaises(ValueError):
            self.renderer.render(self.summary)


if __name__ == "__main__":
    unittest.main()
