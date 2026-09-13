"""Resolution of financial-event amounts whose CSV values are blank."""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol


class MissingAmountResolver(ABC):
    """Interface for resolving one blank ``financial_events.amount`` value."""

    @abstractmethod
    def resolve(self, event_id: str) -> ResolvedAmount | None:
        """Return a non-zero resolved amount or ``None`` if not resolvable."""


class ImageAmountExtractor(Protocol):
    """Protocol for image extraction implementations."""

    def extract_amount(self, image_path: Path) -> Decimal | str | None:
        ...


class ImageAmountResolutionError(ValueError):
    """Raised when extracted image amount is invalid, non-positive, or NaN."""


class NoImageAmountExtractor:
    """Default extractor that always returns None, triggering fallback."""

    def extract_amount(self, image_path: Path) -> None:
        return None


@dataclass(frozen=True)
class ResolvedAmount:
    event_id: str
    image_id: str
    image_path: Path
    amount: Decimal
    source: str


MANUAL_IMAGE_AMOUNTS: dict[str, Decimal] = {
    "image_01": Decimal("4365000"),
    "image_02": Decimal("100000"),
    "image_03": Decimal("41772"),
    "image_04": Decimal("2854"),
    "image_05": Decimal("704.05"),
    "image_06": Decimal("1995"),
    "image_07": Decimal("8528.10"),
    "image_08": Decimal("15339"),
    "image_09": Decimal("723"),
    "image_10": Decimal("79679.26"),
    "image_11": Decimal("3650"),
    "image_12": Decimal("33.50"),
    "image_13": Decimal("2298"),
    "image_14": Decimal("4543"),
    "image_15": Decimal("9968"),
    "image_16": Decimal("393.22"),
}


class ImageBackedMissingAmountResolver(MissingAmountResolver):
    """Resolve an event via ``images.csv``, its PNG, and a controlled fallback."""

    def __init__(
        self,
        dataset_dir: str | Path,
        extractor: ImageAmountExtractor | None = None,
        manual_amounts_by_image: dict[str, Decimal] | None = None,
    ):
        self.dataset_dir = Path(dataset_dir)
        self.extractor = extractor if extractor else NoImageAmountExtractor()
        self.manual_amounts_by_image = (
            MANUAL_IMAGE_AMOUNTS
            if manual_amounts_by_image is None
            else manual_amounts_by_image
        )
        self._image_by_event: dict[str, str] = {}

        images_csv = self.dataset_dir / "images.csv"
        with images_csv.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                event_id = row["related_event_id"]
                if event_id in self._image_by_event:
                    raise ValueError(f"Multiple images reference event_id {event_id}")
                self._image_by_event[event_id] = row["image_id"]

    def resolve(self, event_id: str) -> ResolvedAmount | None:
        image_id = self._image_by_event.get(event_id)
        if image_id is None:
            return None

        image_path = self.dataset_dir / "media" / "images" / f"{image_id}.png"
        if not image_path.exists():
            raise FileNotFoundError(f"Missing evidence image file: {image_path}")

        extracted = self.extractor.extract_amount(image_path)
        if extracted is not None:
            amount = _validate_amount(extracted)
            return ResolvedAmount(
                event_id=event_id,
                image_id=image_id,
                image_path=image_path,
                amount=amount,
                source="image_extractor",
            )

        manual = self.manual_amounts_by_image.get(image_id)
        if manual is not None:
            amount = _validate_amount(manual)
            return ResolvedAmount(
                event_id=event_id,
                image_id=image_id,
                image_path=image_path,
                amount=amount,
                source="manual_fallback",
            )

        return None


def _validate_amount(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise ImageAmountResolutionError("Boolean is not an amount")
    try:
        amount = Decimal(str(value)) if not isinstance(value, Decimal) else value
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ImageAmountResolutionError(f"Invalid amount representation: {value}") from exc

    if amount.is_nan() or amount.is_infinite() or amount <= Decimal("0"):
        raise ImageAmountResolutionError(f"Amount must be positive and finite, got {amount}")

    return amount

