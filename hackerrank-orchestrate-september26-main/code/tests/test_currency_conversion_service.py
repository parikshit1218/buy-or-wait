import csv
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from currency_conversion_service import CurrencyConversionService, MissingExchangeRateError


class CurrencyConversionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dataset = Path(self.temp_dir.name)
        self._write_rates([
            ["2026-01-15", "EUR", "USD", "1.09"],
            ["2026-01-15", "EUR", "ZAR", "20"],
            ["2026-01-15", "USD", "EUR", "0.92"],
            ["2026-01-15", "USD", "IDR", "15833.33"],
            ["2026-01-15", "USD", "INR", "83.33"],
        ])
        self.service = CurrencyConversionService(self.dataset)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_rates(self, rows):
        with (self.dataset / "exchange_rates.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["rate_date", "from_currency", "to_currency", "rate"])
            writer.writerows(rows)

    def test_each_currency_pair_present_in_dataset_uses_its_exact_direction(self):
        cases = [
            ("EUR", "USD", Decimal("1.09"), Decimal("13.45605")),
            ("EUR", "ZAR", Decimal("20"), Decimal("246.900")),
            ("USD", "EUR", Decimal("0.92"), Decimal("11.35740")),
            ("USD", "IDR", Decimal("15833.33"), Decimal("195462.45885")),
            ("USD", "INR", Decimal("83.33"), Decimal("1028.70885")),
        ]
        for source, target, rate, expected in cases:
            with self.subTest(source=source, target=target):
                result = self.service.convert(Decimal("12.345"), source, target, date(2026, 1, 15))
                self.assertEqual(rate, result.rate)
                self.assertEqual(expected, result.converted_amount)

    def test_regression_dataset_contains_exactly_the_observed_currency_directions(self):
        repository_dataset = Path(__file__).resolve().parents[2] / "dataset"
        service = CurrencyConversionService(repository_dataset)
        self.assertEqual(
            {
                ("EUR", "USD"), ("EUR", "ZAR"), ("USD", "EUR"),
                ("USD", "IDR"), ("USD", "INR"),
            },
            service.supplied_pairs(),
        )

    def test_regression_real_dataset_rates_convert_every_observed_pair(self):
        repository_dataset = Path(__file__).resolve().parents[2] / "dataset"
        service = CurrencyConversionService(repository_dataset)
        expected = {
            ("EUR", "USD"): Decimal("1.09"),
            ("EUR", "ZAR"): Decimal("20"),
            ("USD", "EUR"): Decimal("0.92"),
            ("USD", "IDR"): Decimal("15833.33"),
            ("USD", "INR"): Decimal("83.33"),
        }
        for (source, target), rate in expected.items():
            with self.subTest(source=source, target=target):
                result = service.convert(Decimal("1"), source, target, "2026-01-15")
                self.assertEqual(rate, result.converted_amount)

    def test_preserves_decimal_precision_without_float_rounding(self):
        result = self.service.convert(Decimal("0.1"), "USD", "IDR", "2026-01-15")
        self.assertIsInstance(result.converted_amount, Decimal)
        self.assertEqual(Decimal("1583.333"), result.converted_amount)

    def test_same_currency_conversion_needs_no_rate(self):
        result = self.service.convert(Decimal("17.005"), "USD", "USD", "2024-01-01")
        self.assertEqual(Decimal("1"), result.rate)
        self.assertEqual(Decimal("17.005"), result.converted_amount)

    def test_missing_exact_date_is_not_filled_from_another_date(self):
        with self.assertRaisesRegex(MissingExchangeRateError, "EUR->USD on 2026-01-14"):
            self.service.convert(Decimal("1"), "EUR", "USD", "2026-01-14")

    def test_missing_requested_direction_is_not_inverted_or_triangulated(self):
        with self.assertRaisesRegex(MissingExchangeRateError, "USD->ZAR on 2026-01-15"):
            self.service.convert(Decimal("1"), "USD", "ZAR", "2026-01-15")

    def test_rejects_non_decimal_amounts(self):
        with self.assertRaises(TypeError):
            self.service.convert(1.5, "EUR", "USD", "2026-01-15")

    def test_duplicate_dataset_rate_key_is_rejected(self):
        self._write_rates([
            ["2026-01-15", "EUR", "USD", "1.09"],
            ["2026-01-15", "EUR", "USD", "1.10"],
        ])
        with self.assertRaises(ValueError):
            CurrencyConversionService(self.dataset)


if __name__ == "__main__":
    unittest.main()
