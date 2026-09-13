"""Unit tests for Phase 1 foundational modules: models, loader, currency, validator, CLI."""

import io
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add parent code/ directory to path
CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from config import DEFAULT_DATASET_DIR, Config
from currency import CurrencyConverter, MissingExchangeRateError
from data_loader import DataLoader, parse_bool, parse_date, parse_decimal
from main import run_check_data
from models import (
    FinancialProfile,
    FinancialRequest,
    OutputRow,
    PaymentOption,
    SampleRequest,
)
from validators import validate_dataset


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = DataLoader(DEFAULT_DATASET_DIR)
        cls.ctx = cls.loader.load_all()

    def test_all_monetary_values_are_decimal(self):
        """Verify that all loaded monetary amounts strictly use Decimal, never float."""
        for p in self.ctx.profiles:
            self.assertIsInstance(p.current_available_balance, Decimal)
            self.assertIsInstance(p.minimum_balance_to_keep, Decimal)

        for r in self.ctx.requests:
            self.assertIsInstance(r.requested_amount, Decimal)

        for ev in self.ctx.events:
            if ev.amount is not None:
                self.assertIsInstance(ev.amount, Decimal)
            if ev.minimum_allowed_amount is not None:
                self.assertIsInstance(ev.minimum_allowed_amount, Decimal)

        for opt in self.ctx.payment_options:
            self.assertIsInstance(opt.payment_amount, Decimal)
            self.assertIsInstance(opt.financing_fee, Decimal)
            self.assertIsInstance(opt.total_payable_amount, Decimal)

        for rate in self.ctx.exchange_rates:
            self.assertIsInstance(rate.rate, Decimal)

    def test_safe_date_and_type_parsing(self):
        self.assertEqual(date(2026, 9, 13), parse_date("2026-09-13"))
        self.assertEqual(Decimal("12345.67"), parse_decimal("12,345.67"))
        self.assertTrue(parse_bool("true"))
        self.assertTrue(parse_bool("True"))
        self.assertFalse(parse_bool("false"))
        self.assertFalse(parse_bool("0"))

    def test_indexes_integrity(self):
        """Verify all 6 required reusable indexes exist and are properly populated."""
        # 1. user_id
        self.assertEqual(275, len(self.ctx.profiles_by_user))
        self.assertEqual(250, sum(len(reqs) for reqs in self.ctx.requests_by_user.values()))
        self.assertEqual(25342, sum(len(evs) for evs in self.ctx.events_by_user.values()))

        # 2. request_id
        self.assertEqual(250, len(self.ctx.requests_by_id))
        self.assertEqual(25, len(self.ctx.sample_requests_by_id))
        self.assertEqual(275, len(self.ctx.all_requests_by_id))
        self.assertEqual(790, sum(len(opts) for opts in self.ctx.options_by_request.values()))

        # 3. event_id
        self.assertEqual(25342, len(self.ctx.events_by_id))
        self.assertIn("event_01", self.ctx.events_by_id)

        # 4. payment_option_id
        self.assertEqual(790, len(self.ctx.options_by_id))
        self.assertIn("payment_option_01", self.ctx.options_by_id)

        # 5. image_id
        self.assertEqual(16, len(self.ctx.images_by_id))
        self.assertIn("image_01", self.ctx.images_by_id)

        # 6. related_event_id
        self.assertEqual(16, len(self.ctx.images_by_related_event))
        self.assertIn("event_253", self.ctx.images_by_related_event)
        self.assertEqual("image_01", self.ctx.images_by_related_event["event_253"].image_id)

    def test_currency_converter_exact_lookups(self):
        converter = self.ctx.currency_converter

        # Same currency
        same = converter.convert(Decimal("100"), "USD", "USD", date(2026, 1, 15))
        self.assertEqual(Decimal("100"), same.converted_amount)
        self.assertEqual(Decimal("1"), same.rate)

        # Exact dated rate
        res = converter.convert(Decimal("10"), "EUR", "USD", date(2026, 1, 15))
        self.assertEqual(Decimal("1.09"), res.rate)
        self.assertEqual(Decimal("10.90"), res.converted_amount)

        # Missing date raises MissingExchangeRateError
        with self.assertRaises(MissingExchangeRateError):
            converter.convert(Decimal("10"), "EUR", "USD", date(1999, 1, 1))

        # Rejects float
        with self.assertRaises(TypeError):
            converter.convert(10.0, "EUR", "USD", date(2026, 1, 15))

    def test_dataset_validator_clean(self):
        media_dir = DEFAULT_DATASET_DIR / "media" / "images"
        report = validate_dataset(self.ctx, media_dir=media_dir)
        self.assertTrue(report.is_valid)
        self.assertEqual(0, len(report.errors))
        self.assertEqual(0, sum(report.missing_joins.values()))
        self.assertEqual(16, report.blank_event_amounts)
        self.assertEqual(250, report.total_requests)
        self.assertEqual(25, report.total_samples)
        self.assertEqual(275, report.total_profiles)

    def test_cli_check_data_runs_successfully(self):
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = run_check_data(DEFAULT_DATASET_DIR)
        output_text = out.getvalue()

        self.assertEqual(0, exit_code)
        self.assertIn("Number of evaluation requests:   250", output_text)
        self.assertIn("Number of sample requests:       25", output_text)
        self.assertIn("Number of profiles:              275", output_text)
        self.assertIn("Number of financial events:      25342", output_text)
        self.assertIn("Number of payment options:       790", output_text)
        self.assertIn("Number of messages:              215", output_text)
        self.assertIn("Number of images:                16", output_text)
        self.assertIn("Blank financial-event amounts:   16", output_text)
        self.assertIn("Currencies:                      EUR, IDR, INR, USD, ZAR", output_text)
        self.assertIn("Missing joins:                   0", output_text)
        self.assertIn("ALL DATA INTEGRITY CHECKS PASSED", output_text)

    def test_output_row_serialization(self):
        row = OutputRow(
            request_id="request_26",
            amount_safe_to_pay=Decimal("150.50"),
            affordability_status="affordable_now",
            recommended_payment_method="full_payment",
            payment_plan="2026-09-01:150.50",
            earliest_date_for_full_payment=date(2026, 9, 1),
            spending_changes_needed="none",
            decision_explanation="Safe to pay in full today.",
        )
        d = row.to_csv_dict()
        self.assertEqual("request_26", d["request_id"])
        self.assertEqual("150.50", d["amount_safe_to_pay"])
        self.assertEqual("2026-09-01", d["earliest_date_for_full_payment"])


if __name__ == "__main__":
    unittest.main()
