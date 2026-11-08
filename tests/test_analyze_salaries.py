"""Synthetic checks for the November 2026 aggregate salary audit utility."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_salaries.py"
SPEC = importlib.util.spec_from_file_location("analyze_salaries", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def row(**changes):
    values = dict(zip(audit.FIELDS, ["2022", "MI", "FT", "Example Analyst", "100000",
                                   "USD", "100000", "US", "50", "US", "M"]))
    values.update(changes)
    return values


class AggregateChecks(unittest.TestCase):
    def test_duplicate_records_are_counted_and_retained_in_means(self):
        result = audit.analyze_rows(list(audit.FIELDS), [row(), row(), row(salary_in_usd="400000")])
        self.assertEqual(result["row_count"], 3)
        self.assertEqual(result["distinct_row_count"], 2)
        self.assertEqual(result["duplicate_row_occurrences"], 1)
        self.assertEqual(result["salary_validity"]["salary_in_usd"]["mean"], 200000)

    def test_zero_negative_and_invalid_salary_values_are_flagged_without_losing_rows(self):
        records = [row(salary_in_usd=value) for value in ["0", "-5", "NaN", "Infinity", "bad", "", "10"]]
        result = audit.analyze_rows(list(audit.FIELDS), records)
        check = result["salary_validity"]["salary_in_usd"]
        self.assertEqual((result["row_count"], check["valid_positive_count"], check["invalid_or_nonpositive_count"]), (7, 1, 6))
        self.assertEqual(check["mean"], 10)
        self.assertEqual(result["remote_ratio_groups"][0]["row_count"], 7)
        self.assertEqual(result["remote_ratio_groups"][0]["valid_positive_usd_count"], 1)

    def test_threshold_boundary_is_reported_separately(self):
        result = audit.analyze_rows(list(audit.FIELDS), [row(salary_in_usd=str(v)) for v in [199999, 200000, 200001]])
        check = result["salary_validity"]["salary_in_usd"]
        self.assertEqual(check["at_least_200000_count"], 2)
        self.assertEqual(check["greater_than_200000_count"], 1)
        self.assertEqual(check["exactly_200000_count"], 1)

    def test_enum_and_year_validity_do_not_silently_drop_records(self):
        result = audit.analyze_rows(list(audit.FIELDS), [row(), row(experience_level="UNKNOWN", company_size="XL", remote_ratio="25", work_year="bad")])
        self.assertEqual(result["enum_validity"]["experience_level"]["invalid_values"], {"UNKNOWN": 1})
        self.assertEqual(result["enum_validity"]["remote_ratio"]["invalid_row_count"], 1)
        self.assertEqual(result["year_counts"], {"2022": 1})
        self.assertEqual(result["invalid_year_row_count"], 1)
        self.assertEqual(sum(g["row_count"] for g in result["experience_groups"]), 2)

    def test_overall_mean_is_weighted_by_records_and_country_scopes_differ(self):
        records = [row(company_size="S", salary_in_usd="400000", employee_residence="GB"),
                   row(salary_in_usd="100000", employee_residence="DE"), row(salary_in_usd="100000")]
        result = audit.analyze_rows(list(audit.FIELDS), records)
        self.assertEqual(result["salary_validity"]["salary_in_usd"]["mean"], 200000)
        self.assertEqual(result["country_scope"]["employee_residence"]["distinct_country_code_count"], 3)
        self.assertEqual(result["country_scope"]["company_location"]["distinct_country_code_count"], 1)
        self.assertEqual([g["row_count"] for g in result["company_size_groups"]], [2, 1])

    def test_missing_duplicate_columns_and_malformed_row_width_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing required"):
            audit.analyze_rows(list(audit.FIELDS[:-1]), [])
        with self.assertRaisesRegex(ValueError, "Duplicate column"):
            audit.analyze_rows([*audit.FIELDS, "salary"], [])
        broken = row()
        broken["salary"] = None
        with self.assertRaisesRegex(ValueError, "Row width"):
            audit.analyze_rows(list(audit.FIELDS), [broken])


class FileChecks(unittest.TestCase):
    def write_csv(self, path):
        data = io.StringIO(newline="")
        writer = csv.DictWriter(data, fieldnames=audit.FIELDS)
        writer.writeheader()
        writer.writerows([row(), row(salary_in_usd="200000")])
        path.write_text(data.getvalue())

    def test_cli_is_read_only_and_emits_no_rows_or_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.csv"
            output = Path(temp) / "summary.json"
            self.write_csv(source)
            before = source.read_bytes()
            self.assertEqual(audit.main([str(source), "--output", str(output)]), 0)
            self.assertEqual(source.read_bytes(), before)
            text = output.read_text()
            data = json.loads(text)
            self.assertEqual(data["row_count"], 2)
            self.assertEqual(len(data["source_sha256"]), 64)
            self.assertNotIn(str(source), text)
            self.assertNotIn("\"records\"", text)
            self.assertFalse(data["method"]["row_level_records_emitted"])

    def test_output_collision_and_symlink_alias_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.csv"
            alias = Path(temp) / "alias.csv"
            self.write_csv(source)
            alias.symlink_to(source)
            before = source.read_bytes()
            for target in [source, alias]:
                with self.assertRaises(SystemExit) as raised:
                    audit.main([str(source), "--output", str(target)])
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
