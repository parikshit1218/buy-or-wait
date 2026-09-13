"""Unit tests for SafeNowCalculator."""

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment
from safe_now_calculator import SafeNowCalculator


class SafeNowCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.engine = ForecastEngine()
        self.calculator = SafeNowCalculator(self.engine)
        self.request_date = date(2026, 1, 10)

    def state(self, balance="1000", minimum="200", events=()):
        items = tuple(events)
        return FinancialState(
            request_id="r1",
            user_id="u1",
            request_date=self.request_date,
            home_currency="USD",
            available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            events=items,
            recurring_expenses=(),
            one_time_expenses=(),
            confirmed_income=tuple(e for e in items if e.is_confirmed_income),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    @staticmethod
    def event(event_id, *, day, amount, direction="debit", income=False):
        return NormalizedEvent(
            event_id=event_id,
            user_id="u1",
            event_type="income" if income else "expense",
            description=event_id,
            category="salary" if income else "utilities",
            direction=direction,
            amount=Decimal(amount),
            currency="USD",
            amount_home_currency=Decimal(amount),
            conversion_rate=Decimal("1"),
            conversion_rate_date=day,
            amount_source="test",
            event_date=day,
            settlement_date=day,
            status="scheduled" if income else "settled",
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None,
            financial_meaning="income" if income else "expense",
            is_recurring=False,
            is_confirmed_income=income,
            is_confirmed_future_payment=direction == "debit",
            is_refund=False,
            is_transfer=False,
            included_in_cash_state=True,
            exclusion_reason=None,
            evidence_resolution=None,
        )

    def test_full_amount_safe(self):
        # Balance = 1000, Min = 200 -> Margin = 800. Request = 500.
        state = self.state(balance="1000", minimum="200")
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("500"))
        self.assertEqual(Decimal("500"), safe_amt)

    def test_partial_amount_safe(self):
        # Balance = 1000, Min = 200 -> Margin = 800. Request = 1200.
        state = self.state(balance="1000", minimum="200")
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("1200"))
        self.assertEqual(Decimal("800"), safe_amt)

    def test_zero_safe_amount_when_already_at_or_below_minimum(self):
        # Balance = 200, Min = 200 -> Margin = 0.
        state = self.state(balance="200", minimum="200")
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("100"))
        self.assertEqual(Decimal("0"), safe_amt)

        # Balance = 150, Min = 200 -> Margin = -50 -> Safe = 0.
        state_under = self.state(balance="150", minimum="200")
        safe_amt_under = self.calculator.calculate_safe_amount(state_under, Decimal("100"))
        self.assertEqual(Decimal("0"), safe_amt_under)

    def test_exact_boundary_conditions(self):
        # Margin exactly equals requested amount
        state = self.state(balance="500", minimum="200")  # Margin = 300
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("300"))
        self.assertEqual(Decimal("300"), safe_amt)

    def test_upcoming_mandatory_expenses_cap_safe_now(self):
        # Balance = 1000, Min = 200. Upcoming rent of 600 in 5 days.
        # Lowest balance will be 400 on day 5 -> Margin = 400 - 200 = 200.
        rent_event = self.event("rent", day=self.request_date + timedelta(days=5), amount="600")
        state = self.state(balance="1000", minimum="200", events=[rent_event])
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("500"))
        self.assertEqual(Decimal("200"), safe_amt)

    def test_multiple_expenses_cumulative_reduction(self):
        # Balance = 1000, Min = 200.
        # Event 1: -300 on day 2 (bal = 700)
        # Event 2: -400 on day 10 (bal = 300) -> lowest balance = 300 -> Margin = 100.
        e1 = self.event("e1", day=self.request_date + timedelta(days=2), amount="300")
        e2 = self.event("e2", day=self.request_date + timedelta(days=10), amount="400")
        state = self.state(balance="1000", minimum="200", events=[e1, e2])
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("500"))
        self.assertEqual(Decimal("100"), safe_amt)

    def test_future_income_after_dip_does_not_inflate_safe_now(self):
        # Balance = 1000, Min = 200.
        # Debit: -700 on day 3 (bal = 300 -> Margin = 100).
        # Salary: +2000 on day 15 (bal = 2300).
        # Safe amount today must still be 100 (capped by day 3 dip).
        debit = self.event("debit", day=self.request_date + timedelta(days=3), amount="700")
        salary = self.event("salary", day=self.request_date + timedelta(days=15), amount="2000", direction="credit", income=True)
        state = self.state(balance="1000", minimum="200", events=[debit, salary])
        safe_amt = self.calculator.calculate_safe_amount(state, Decimal("500"))
        self.assertEqual(Decimal("100"), safe_amt)

    def test_rejection_of_invalid_inputs(self):
        state = self.state()
        with self.assertRaises(TypeError):
            self.calculator.calculate_safe_amount(state, 100.0)  # type: ignore
        with self.assertRaises(ValueError):
            self.calculator.calculate_safe_amount(state, Decimal("-10"))


if __name__ == "__main__":
    unittest.main()

