import csv
import sys
import tempfile
import unittest
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from missing_amount_resolver import (
    ImageAmountResolutionError,
    ImageBackedMissingAmountResolver,
    MANUAL_IMAGE_AMOUNTS,
    MissingAmountResolver,
    ResolvedAmount,
)


@dataclass
class StubExtractor:
    value: Decimal | str | None
    called_with: Path | None = None

    def extract_amount(self, image_path: Path) -> Decimal | str | None:
        self.called_with = image_path
        return self.value


class MissingAmountResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dataset = Path(self.temp_dir.name)
        (self.dataset / "media" / "images").mkdir(parents=True)
        self._write_index([["image_test", "u1", "r1", "event_test"]])
        (self.dataset / "media" / "images" / "image_test.png").write_bytes(b"not-decoded-in-unit-test")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_index(self, rows):
        with (self.dataset / "images.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["image_id", "user_id", "request_id", "related_event_id"])
            writer.writerows(rows)

    def test_missing_amount_resolver_is_an_interface(self):
        self.assertTrue(hasattr(MissingAmountResolver, "resolve"))
        with self.assertRaises(TypeError):
            MissingAmountResolver()

    def test_resolves_event_through_images_index_and_mocked_extractor(self):
        extractor = StubExtractor(Decimal("1234.50"))
        resolver = ImageBackedMissingAmountResolver(self.dataset, extractor=extractor, manual_amounts_by_image={})
        result = resolver.resolve("event_test")
        self.assertEqual(Decimal("1234.50"), result.amount)
        self.assertEqual("image_extractor", result.source)
        self.assertEqual("image_test", result.image_id)
        self.assertEqual(self.dataset / "media" / "images" / "image_test.png", extractor.called_with)

    def test_uses_deterministic_manual_fallback_when_extractor_returns_none(self):
        resolver = ImageBackedMissingAmountResolver(
            self.dataset, extractor=StubExtractor(None), manual_amounts_by_image={"image_test": Decimal("87.65")}
        )
        result = resolver.resolve("event_test")
        self.assertEqual(Decimal("87.65"), result.amount)
        self.assertEqual("manual_fallback", result.source)

    def test_returns_none_for_event_without_image_mapping_and_never_returns_zero(self):
        resolver = ImageBackedMissingAmountResolver(self.dataset, manual_amounts_by_image={})
        self.assertIsNone(resolver.resolve("unknown_event"))

    def test_missing_evidence_file_is_an_error(self):
        (self.dataset / "media" / "images" / "image_test.png").unlink()
        resolver = ImageBackedMissingAmountResolver(self.dataset, manual_amounts_by_image={"image_test": Decimal("1")})
        with self.assertRaises(FileNotFoundError):
            resolver.resolve("event_test")

    def test_rejects_invalid_or_negative_mocked_extraction(self):
        for invalid in ("not-an-amount", Decimal("-0.01"), Decimal("NaN"), True):
            with self.subTest(invalid=invalid):
                resolver = ImageBackedMissingAmountResolver(self.dataset, extractor=StubExtractor(invalid), manual_amounts_by_image={})
                with self.assertRaises(ImageAmountResolutionError):
                    resolver.resolve("event_test")

    def test_manual_fallback_covers_every_actual_blank_amount_image(self):
        repository_dataset = Path(__file__).resolve().parents[2] / "dataset"
        with (repository_dataset / "images.csv").open("r", encoding="utf-8", newline="") as handle:
            image_ids = {row["image_id"] for row in csv.DictReader(handle)}
        self.assertEqual(16, len(image_ids))
        self.assertEqual(image_ids, set(MANUAL_IMAGE_AMOUNTS))

    def test_actual_dataset_manual_fallback_returns_decimal_for_each_blank_event(self):
        repository_dataset = Path(__file__).resolve().parents[2] / "dataset"
        resolver = ImageBackedMissingAmountResolver(repository_dataset)
        with (repository_dataset / "images.csv").open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            with self.subTest(event_id=row["related_event_id"]):
                result = resolver.resolve(row["related_event_id"])
                self.assertIsInstance(result.amount, Decimal)
                self.assertGreater(result.amount, Decimal("0"))
                self.assertEqual("manual_fallback", result.source)


if __name__ == "__main__":
    unittest.main()
