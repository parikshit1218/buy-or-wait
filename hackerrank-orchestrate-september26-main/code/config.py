"""Project configuration and path resolution for Buy or Wait?."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def find_repo_root() -> Path:
    """Resolve the repository root directory containing dataset/."""
    current = Path(__file__).resolve().parent
    while current.parent != current:
        if (current / "dataset").is_dir() and (current / "dataset" / "requests.csv").is_file():
            return current
        current = current.parent
    # Fallback to parent of code directory
    return Path(__file__).resolve().parents[1]


REPO_ROOT: Path = find_repo_root()
DEFAULT_DATASET_DIR: Path = REPO_ROOT / "dataset"
DEFAULT_OUTPUT_FILE: Path = REPO_ROOT / "output.csv"

SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"EUR", "IDR", "INR", "USD", "ZAR"})

REQUEST_TYPES: frozenset[str] = frozenset({
    "purchase",
    "travel",
    "education",
    "family_transfer",
    "debt_repayment",
    "investment",
    "housing",
    "emergency_expense",
    "other",
})

AFFORDABILITY_STATUSES: frozenset[str] = frozenset({
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
})

RECOMMENDED_PAYMENT_METHODS: frozenset[str] = frozenset({
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
})

OUTPUT_COLUMNS: tuple[str, ...] = (
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
)

FORECAST_DAYS: int = 90


@dataclass(frozen=True)
class Config:
    """Runtime configuration settings."""

    dataset_dir: Path = DEFAULT_DATASET_DIR
    output_file: Path = DEFAULT_OUTPUT_FILE
    forecast_days: int = FORECAST_DAYS

    @classmethod
    def from_env(cls) -> Config:
        dataset_str = os.getenv("BUY_OR_WAIT_DATASET_DIR")
        output_str = os.getenv("BUY_OR_WAIT_OUTPUT_FILE")
        return cls(
            dataset_dir=Path(dataset_str) if dataset_str else DEFAULT_DATASET_DIR,
            output_file=Path(output_str) if output_str else DEFAULT_OUTPUT_FILE,
        )

