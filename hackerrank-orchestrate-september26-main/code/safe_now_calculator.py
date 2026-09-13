"""Deterministic calculation of amount_safe_to_pay on request_date."""

from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Sequence

from financial_state_service import FinancialState
from forecast_engine import ForecastEngine


ZERO = Decimal("0")


class SafeNowCalculator:
    """Calculates the maximum amount safe to pay today without optional spending changes.

    Mathematical guarantee:
    Paying an amount X on request_date reduces the balance on day 0 through day 90 by exactly X.
    Therefore, the maximum payment X that keeps balance(d) >= minimum_balance_to_keep across
    all 91 forecast days is:
        amount_safe_to_pay = min(requested_amount, max(0, min_t(balance(t) - min_balance)))
    """

    def __init__(self, forecast_engine: ForecastEngine | None = None) -> None:
        self._forecast_engine = forecast_engine or ForecastEngine()

    def calculate_safe_amount(
        self,
        state: FinancialState,
        requested_amount: Decimal,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> Decimal:
        """Return the maximum monetary amount safe to commit on request_date."""
        if not isinstance(requested_amount, Decimal):
            raise TypeError("requested_amount must be a Decimal")
        if requested_amount < ZERO:
            raise ValueError("requested_amount cannot be negative")

        base_result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=(),
            spending_changes=(),
            user_messages=user_messages,
        )

        return min(
            requested_amount,
            max(ZERO, base_result.safety_margin),
        )

