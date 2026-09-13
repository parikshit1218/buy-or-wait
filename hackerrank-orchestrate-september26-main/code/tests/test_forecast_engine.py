import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment


class ForecastEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ForecastEngine()
        self.request_date = date(2026, 1, 10)

    def state(self, *, balance="100", minimum="0", events=(), recurring=()):
        items = tuple(events)
        return FinancialState(
            request_id="r1", user_id="u1", request_date=self.request_date, home_currency="USD",
            available_balance=Decimal(balance), minimum_balance_to_keep=Decimal(minimum), events=items,
            recurring_expenses=tuple(recurring), one_time_expenses=(),
            confirmed_income=tuple(event for event in items if event.is_confirmed_income),
            confirmed_future_payments=(), refunds=(), transfers=(),
        )

    @staticmethod
    def event(event_id, *, day, amount, direction="debit", meaning="expense", status="scheduled", income=False, recurring=False):
        return NormalizedEvent(
            event_id=event_id, user_id="u1", event_type="income" if income else "expense",
            description=event_id if not recurring else "Monthly subscription", category="salary" if income else "utilities",
            direction=direction, amount=Decimal(amount), currency="USD", amount_home_currency=Decimal(amount),
            conversion_rate=Decimal("1"), conversion_rate_date=day, amount_source="test", event_date=day,
            settlement_date=day, status=status, linked_event_id=None, flexibility="fixed",
            minimum_allowed_amount=None, financial_meaning=meaning, is_recurring=recurring,
            is_confirmed_income=income, is_confirmed_future_payment=direction == "debit" and status in {"pending", "scheduled"},
            is_refund=meaning == "refund", is_transfer=False, included_in_cash_state=True,
            exclusion_reason=None, evidence_resolution=None,
        )

    def test_salary_before_purchase_keeps_plan_safe(self):
        salary = self.event("salary", day=date(2026, 1, 10), amount="50", direction="credit", meaning="income", income=True)
        result = self.engine.forecast(self.state(balance="100", minimum="20", events=[salary]), [ProposedPayment(date(2026, 1, 11), Decimal("120"))])
        self.assertEqual(Decimal("30"), result.daily_balances[date(2026, 1, 11)])
        self.assertTrue(result.safe)

    def test_salary_after_purchase_does_not_retroactively_make_plan_safe(self):
        salary = self.event("salary", day=date(2026, 1, 11), amount="50", direction="credit", meaning="income", income=True)
        result = self.engine.forecast(self.state(balance="100", minimum="20", events=[salary]), [ProposedPayment(date(2026, 1, 10), Decimal("120"))])
        self.assertEqual(Decimal("-20"), result.daily_balances[date(2026, 1, 10)])
        self.assertFalse(result.safe)
        self.assertEqual(date(2026, 1, 10), result.lowest_balance_date)

    def test_scheduled_rent_is_applied_as_valid_expense(self):
        rent = self.event("rent", day=date(2026, 1, 15), amount="60")
        result = self.engine.forecast(self.state(balance="100", minimum="40", events=[rent]))
        self.assertEqual(Decimal("40"), result.daily_balances[date(2026, 1, 15)])
        self.assertTrue(result.safe)

    def test_recurring_subscription_is_projected_from_supported_history(self):
        history = [
            self.event("sub_oct", day=date(2025, 10, 16), amount="10", recurring=True),
            self.event("sub_nov", day=date(2025, 11, 15), amount="10", recurring=True),
            self.event("sub_dec", day=date(2025, 12, 15), amount="10", recurring=True),
        ]
        result = self.engine.forecast(self.state(balance="100", events=history, recurring=history))
        self.assertEqual(Decimal("90"), result.daily_balances[date(2026, 1, 15)])
        self.assertEqual(Decimal("70"), result.daily_balances[date(2026, 3, 15)])


    def test_multiple_same_day_events_are_aggregated_before_end_of_day_check(self):
        salary = self.event("salary", day=self.request_date, amount="40", direction="credit", meaning="income", income=True)
        rent = self.event("rent", day=self.request_date, amount="30")
        result = self.engine.forecast(self.state(balance="100", events=[salary, rent]), [ProposedPayment(self.request_date, Decimal("20"))])
        self.assertEqual(Decimal("90"), result.daily_balances[self.request_date])

    def test_minimum_balance_exactly_reached_is_safe(self):
        result = self.engine.forecast(self.state(balance="100", minimum="50"), [ProposedPayment(self.request_date, Decimal("50"))])
        self.assertTrue(result.safe)
        self.assertEqual(Decimal("0"), result.safety_margin)

    def test_balance_below_minimum_is_unsafe(self):
        result = self.engine.forecast(self.state(balance="100", minimum="50"), [ProposedPayment(self.request_date, Decimal("50.01"))])
        self.assertFalse(result.safe)
        self.assertEqual(Decimal("-0.01"), result.safety_margin)

    def test_90_day_boundary_is_inclusive_and_day_91_is_excluded(self):
        day_90 = date(2026, 4, 10)
        day_91 = date(2026, 4, 11)
        inside = self.event("inside", day=day_90, amount="10")
        outside = self.event("outside", day=day_91, amount="20")
        result = self.engine.forecast(self.state(balance="100", events=[inside, outside]))
        self.assertEqual(91, len(result.daily_balances))
        self.assertEqual(Decimal("90"), result.daily_balances[day_90])
        self.assertNotIn(day_91, result.daily_balances)

    def test_rejects_float_payment_amounts(self):
        with self.assertRaises(TypeError):
            self.engine.forecast(self.state(), [ProposedPayment(self.request_date, 1.5)])


if __name__ == "__main__":
    unittest.main()
