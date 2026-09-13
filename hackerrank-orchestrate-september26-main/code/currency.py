"""Deterministic dated currency conversion using only supplied exchange rates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from models import ExchangeRate


class MissingExchangeRateError(LookupError):
    """Raised when the dataset has no exact dated rate in the requested direction."""


@dataclass(frozen=True)
class ConversionResult:
    """Result of a deterministic currency conversion."""

    amount: Decimal
    from_currency: str
    to_currency: str
    rate_date: date
    rate: Decimal
    converted_amount: Decimal


class CurrencyConverter:
    """Exact-match dated currency converter.

    Never interpolates across dates, inverts rates, or triangulates through
    intermediate currencies.
    """

    def __init__(self, rates: list[ExchangeRate] | None = None, dataset_dir: str | Path | None = None):
        self._rates: dict[tuple[date, str, str], ExchangeRate] = {}

        if rates is not None:
            for r in rates:
                key = (r.rate_date, r.from_currency.upper(), r.to_currency.upper())
                if key in self._rates:
                    raise ValueError(f"Duplicate exchange rate for {key}")
                self._rates[key] = r
        elif dataset_dir is not None:
            csv_path = Path(dataset_dir) / "exchange_rates.csv"
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    rate_date = datetime.strptime(row["rate_date"], "%Y-%m-%d").date()
                    from_curr = row["from_currency"].upper()
                    to_curr = row["to_currency"].upper()
                    rate = Decimal(row["rate"])
                    item = ExchangeRate(rate_date=rate_date, from_currency=from_curr, to_currency=to_curr, rate=rate)
                    key = (rate_date, from_curr, to_curr)
                    if key in self._rates:
                        raise ValueError(f"Duplicate exchange rate for {key}")
                    self._rates[key] = item

    def get_rate(self, from_currency: str, to_currency: str, rate_date: date | str) -> Decimal:
        """Return the exact exchange rate for (from_currency, to_currency, rate_date)."""
        res = self.convert(Decimal("1"), from_currency, to_currency, rate_date)
        return res.rate

    def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: date | str,
    ) -> ConversionResult:
        """Convert amount using exact (rate_date, from_currency, to_currency) rate.

        Same-currency conversions require no rate entry and return unchanged.
        """
        if not isinstance(amount, Decimal):
            raise TypeError(f"amount must be Decimal, got {type(amount).__name__}")

        parsed_date = (
            datetime.strptime(rate_date, "%Y-%m-%d").date()
            if isinstance(rate_date, str)
            else rate_date
        )
        source = from_currency.upper()
        target = to_currency.upper()

        if source == target:
            return ConversionResult(
                amount=amount,
                from_currency=source,
                to_currency=target,
                rate_date=parsed_date,
                rate=Decimal("1"),
                converted_amount=amount,
            )

        key = (parsed_date, source, target)
        rate_entry = self._rates.get(key)
        if rate_entry is None:
            raise MissingExchangeRateError(
                f"No supplied rate for {source}->{target} on {parsed_date.isoformat()}"
            )

        return ConversionResult(
            amount=amount,
            from_currency=source,
            to_currency=target,
            rate_date=parsed_date,
            rate=rate_entry.rate,
            converted_amount=amount * rate_entry.rate,
        )

    def supplied_pairs(self) -> frozenset[tuple[str, str]]:
        """Return the unique set of currency pairs present in the exchange rates."""
        return frozenset((rate.from_currency, rate.to_currency) for rate in self._rates.values())
