"""Find the first date on which a one-time full payment is forecast-safe."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from financial_state_service import FinancialState
from forecast_engine import ForecastEngine, ProposedPayment, SpendingChange


class EarliestFullPaymentService:
    """Search the inclusive 90-day horizon without considering preferences."""

    def __init__(self, forecast_engine: ForecastEngine | None = None):
        self._forecast_engine = forecast_engine or ForecastEngine()

    def find_earliest_date(
        self,
        state: FinancialState,
        requested_amount: Decimal,
        spending_changes: Sequence[SpendingChange] = (),
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> date | None:
        """Return the first date a full one-time payment passes all safety days.

        Each candidate is evaluated by a fresh forecast from ``request_date``
        through ``request_date + 90 days``. No payment-method preferences or
        payment options are consulted; this is strictly a capacity measure.
        ``None`` represents the required empty earliest-full-payment value.
        """

        if not isinstance(requested_amount, Decimal):
            raise TypeError("requested_amount must be Decimal")
        if requested_amount < Decimal("0"):
            raise ValueError("requested_amount cannot be negative")

        final_date = state.request_date + timedelta(days=ForecastEngine.FORECAST_DAYS)
        candidate = state.request_date
        while candidate <= final_date:
            result = self._forecast_engine.forecast(
                state=state,
                proposed_payment_plan=(ProposedPayment(payment_date=candidate, amount=requested_amount),),
                spending_changes=spending_changes,
                user_messages=user_messages,
            )
            if result.safe:
                return candidate
            candidate += timedelta(days=1)
        return None
