"""Unit and integration test for the final prediction pipeline and output.csv validation."""

import csv
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import REPO_ROOT
from data_loader import DataLoader
from validators import validate_output_file


class PipelineOutputTests(unittest.TestCase):
    def setUp(self):
        self.output_path = REPO_ROOT / "output.csv"
        self.loader = DataLoader(REPO_ROOT / "dataset")
        self.loader.load_all()
        self.requests = self.loader.load_requests()

    def test_output_file_exists_and_validates(self):
        """Validate output.csv meets all hackathon requirements."""
        self.assertTrue(self.output_path.is_file(), "output.csv must exist at repository root")

        expected_ids = [r.request_id for r in self.requests]
        self.assertEqual(len(expected_ids), 250, "Expected exactly 250 evaluation requests")

        report = validate_output_file(self.output_path, expected_request_ids=expected_ids)
        self.assertTrue(
            report.is_valid,
            f"output.csv validation failed with errors:\n" + "\n".join(f"  - {e}" for e in report.errors),
        )
        self.assertEqual(report.total_requests, 250)

    def test_usage_report_exists_and_conforms(self):
        """Validate code/evaluation/usage_report.md exists and contains all required metrics."""
        report_path = REPO_ROOT / "code" / "evaluation" / "usage_report.md"
        self.assertTrue(report_path.is_file(), "usage_report.md must exist in code/evaluation/")

        content = report_path.read_text(encoding="utf-8")
        required_elements = [
            "Provider",
            "Model",
            "Calls",
            "Input Tokens",
            "Output Tokens",
            "Total Tokens",
            "Average Tokens per Request",
            "Estimated Total Cost",
            "Estimated Cost per Request",
        ]
        for elem in required_elements:
            self.assertIn(elem.lower(), content.lower(), f"Missing required usage report section/metric: {elem}")

        # Ensure no accidental keys or tokens
        self.assertNotIn("AIza", content)
        self.assertNotIn("sk-", content)
        self.assertNotIn("Bearer ", content)


if __name__ == "__main__":
    unittest.main()


