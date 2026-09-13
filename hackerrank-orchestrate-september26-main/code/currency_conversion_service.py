"""Deterministic conversion using only the supplied exchange-rate dataset."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from currency import ConversionResult, CurrencyConverter, MissingExchangeRateError
from models import ExchangeRate


class CurrencyConversionService(CurrencyConverter):
    """Backwards-compatible wrapper around CurrencyConverter."""

    def __init__(self, dataset_dir: str | Path):
        super().__init__(dataset_dir=dataset_dir)
