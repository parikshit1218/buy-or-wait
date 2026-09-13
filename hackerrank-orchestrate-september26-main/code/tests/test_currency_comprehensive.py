"""Comprehensive currency conversion unit and regression tests."""

import csv
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

# Add parent code/ directory to path
CODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_DIR))

from config import DEFAULT_DATASET_DIR
from currency import ConversionResult, CurrencyConverter, MissingExchangeRateError
from data_loader import DataLoader
from models import ExchangeRate


class ComprehensiveCurrencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.converter = CurrencyConverter(dataset_dir=DEFAULT_DATASET_DIR)
        cls.loader = DataLoader(DEFAULT_DATASET_DIR)
        cls.ctx = cls.loader.load_all()

    def test_all_five_supplied_currency_pairs_are_present(self):
        """Verify all 5 directional currency pairs from exchange_rates.csv are indexed."""
        expected_pairs = {
            ("EUR", "USD"),
            ("EUR", "ZAR"),
            ("USD", "EUR"),
            ("USD", "IDR"),
            ("USD", "INR"),
        }
        self.assertEqual(expected_pairs, self.converter.supplied_pairs())

    def test_each_supplied_pair_conversion_sample(self):
        """Test at least one valid conversion for every pair in the dataset."""
        test_cases = [
            ("EUR", "USD", date(2026, 1, 15), Decimal("100"), Decimal("1.09"), Decimal("109.00")),
            ("EUR", "ZAR", date(2026, 1, 15), Decimal("50"), Decimal("20"), Decimal("1000")),
            ("USD", "EUR", date(2026, 1, 15), Decimal("200"), Decimal("0.92"), Decimal("184.00")),
            ("USD", "IDR", date(2026, 1, 15), Decimal("10"), Decimal("15833.33"), Decimal("158333.30")),
            ("USD", "INR", date(2026, 1, 15), Decimal("10"), Decimal("83.33"), Decimal("833.30")),
        ]
        for from_c, to_c, rate_d, amt, expected_rate, expected_converted in test_cases:
            with self.subTest(pair=f"{from_c}->{to_c}", date=rate_d):
                result = self.converter.convert(amt, from_c, to_c, rate_d)
                self.assertIsInstance(result, ConversionResult)
                self.assertEqual(amt, result.amount)
                self.assertEqual(from_c, result.from_currency)
                self.assertEqual(to_c, result.to_currency)
                self.assertEqual(rate_d, result.rate_date)
                self.assertEqual(expected_rate, result.rate)
                self.assertEqual(expected_converted, result.converted_amount)

                # Test helper method get_rate
                rate_val = self.converter.get_rate(from_c, to_c, rate_d)
                self.assertEqual(expected_rate, rate_val)

    def test_all_same_currency_identity_conversions(self):
        """Verify identity conversion works for all currencies without exchange rate lookup."""
        currencies = ["EUR", "IDR", "INR", "USD", "ZAR"]
        test_amount = Decimal("987654.321")
        test_date = date(2026, 6, 30)

        for curr in currencies:
            with self.subTest(currency=curr):
                res = self.converter.convert(test_amount, curr, curr, test_date)
                self.assertEqual(Decimal("1"), res.rate)
                self.assertEqual(test_amount, res.converted_amount)
                self.assertEqual(curr, res.from_currency)
                self.assertEqual(curr, res.to_currency)

    def test_decimal_precision_is_preserved_without_float_rounding(self):
        """Verify arbitrary precision decimal arithmetic is preserved exactly."""
        # USD -> INR rate on 2026-01-15 is 83.33
        small_amount = Decimal("0.000123456789")
        res = self.converter.convert(small_amount, "USD", "INR", "2026-01-15")
        expected = small_amount * Decimal("83.33")
        self.assertEqual(expected, res.converted_amount)
        self.assertIsInstance(res.converted_amount, Decimal)

    def test_missing_rate_date_raises_missing_exchange_rate_error(self):
        """Verify attempting to convert on an unlisted date raises MissingExchangeRateError."""
        with self.assertRaises(MissingExchangeRateError) as cm:
            self.converter.convert(Decimal("100"), "EUR", "USD", date(1999, 12, 31))
        self.assertIn("EUR->USD on 1999-12-31", str(cm.exception))

    def test_missing_direction_raises_missing_exchange_rate_error(self):
        """Verify unsupplied inverse or cross pairs raise MissingExchangeRateError."""
        # USD -> ZAR is not in exchange_rates.csv (only EUR -> ZAR exists)
        with self.assertRaises(MissingExchangeRateError) as cm:
            self.converter.convert(Decimal("100"), "USD", "ZAR", date(2026, 1, 15))
        self.assertIn("USD->ZAR on 2026-01-15", str(cm.exception))

        # INR -> USD is not in exchange_rates.csv (only USD -> INR exists)
        with self.assertRaises(MissingExchangeRateError) as cm:
            self.converter.convert(Decimal("100"), "INR", "USD", date(2026, 1, 15))
        self.assertIn("INR->USD on 2026-01-15", str(cm.exception))

    def test_rejects_non_decimal_types(self):
        """Verify floats and invalid types are rejected strictly."""
        with self.assertRaises(TypeError):
            self.converter.convert(100.50, "EUR", "USD", date(2026, 1, 15))

        with self.assertRaises(TypeError):
            self.converter.convert("100.50", "EUR", "USD", date(2026, 1, 15))

        with self.assertRaises(TypeError):
            self.converter.convert(100, "EUR", "USD", date(2026, 1, 15))

    def test_string_date_parsing_compatibility(self):
        """Verify both str ('YYYY-MM-DD') and datetime.date are accepted."""
        res_str = self.converter.convert(Decimal("10"), "USD", "EUR", "2026-01-15")
        res_date = self.converter.convert(Decimal("10"), "USD", "EUR", date(2026, 1, 15))
        self.assertEqual(res_str, res_date)

    def test_regression_every_actual_dataset_exchange_rate_row(self):
        """Regression test: iterate through every row in exchange_rates.csv and verify convert()."""
        csv_path = DEFAULT_DATASET_DIR / "exchange_rates.csv"
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                count += 1
                r_date = row["rate_date"]
                f_curr = row["from_currency"]
                t_curr = row["to_currency"]
                rate = Decimal(row["rate"])

                res = self.converter.convert(Decimal("1"), f_curr, t_curr, r_date)
                self.assertEqual(rate, res.rate)
                self.assertEqual(rate, res.converted_amount)
            self.assertEqual(134, count)

    def test_regression_every_foreign_event_in_financial_events(self):
        """Regression test: verify all 140 foreign transactions in financial_events.csv convert successfully."""
        profiles_by_user = self.ctx.profiles_by_user
        foreign_count = 0

        for ev in self.ctx.events:
            home_curr = profiles_by_user[ev.user_id].home_currency
            if ev.currency != home_curr:
                foreign_count += 1
                rate_date = ev.settlement_date or ev.event_date
                if ev.amount is not None:
                    res = self.converter.convert(ev.amount, ev.currency, home_curr, rate_date)
                    self.assertIsInstance(res.converted_amount, Decimal)
                    self.assertGreater(res.converted_amount, Decimal("0"))

        self.assertEqual(140, foreign_count)


if __name__ == "__main__":
    unittest.main()

