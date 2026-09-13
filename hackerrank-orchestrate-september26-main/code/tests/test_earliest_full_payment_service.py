"""Unit tests for EarliestFullPaymentService."""

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from earliest_full_payment_service import EarliestFullPaymentService
from financial_state_service import FinancialState, NormalizedEvent


class EarliestFullPaymentServiceTests(unittest.TestCase):
    def setUp(self):
        self.request_date = date(2026, 1, 10)
        self.service = EarliestFullPaymentService()

    def state(self, balance="100", minimum="20", events=()):
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
            confirmed_income=tuple(item for item in items if item.is_confirmed_income),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    @staticmethod
    def income(event_id, payment_date, amount):
        return NormalizedEvent(
            event_id=event_id,
            user_id="u1",
            event_type="income",
            description="Confirmed salary",
            category="salary",
            direction="credit",
            amount=Decimal(amount),
            currency="USD",
            amount_home_currency=Decimal(amount),
            conversion_rate=Decimal("1"),
            conversion_rate_date=payment_date,
            amount_source="test",
            event_date=payment_date,
            settlement_date=payment_date,
            status="scheduled",
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None,
            financial_meaning="income",
            is_recurring=False,
            is_confirmed_income=True,
            is_confirmed_future_payment=False,
            is_refund=False,
            is_transfer=False,
            included_in_cash_state=True,
            exclusion_reason=None,
            evidence_resolution=None,
        )

    def test_request_date_is_returned_when_payment_is_immediately_safe(self):
        # Day 0 boundary (request_date)
        self.assertEqual(self.request_date, self.service.find_earliest_date(self.state(), Decimal("80")))

    def test_first_safe_date_waits_for_confirmed_salary(self):
        salary_date = self.request_date + timedelta(days=3)
        state = self.state(events=[self.income("salary", salary_date, "50")])
        self.assertEqual(salary_date, self.service.find_earliest_date(state, Decimal("120")))

    def test_day_89_candidate_boundary(self):
        day_89 = self.request_date + timedelta(days=89)
        state = self.state(events=[self.income("salary", day_89, "50")])
        self.assertEqual(day_89, self.service.find_earliest_date(state, Decimal("120")))

    def test_day_90_is_included_as_a_candidate_boundary(self):
        day_90 = self.request_date + timedelta(days=90)
        state = self.state(events=[self.income("salary", day_90, "50")])
        self.assertEqual(day_90, self.service.find_earliest_date(state, Decimal("120")))

    def test_day_91_is_excluded_and_returns_none(self):
        # Salary on day 91 is beyond the 90-day horizon -> cannot be used to afford payment in 90 days
        day_91 = self.request_date + timedelta(days=91)
        state = self.state(events=[self.income("salary", day_91, "50")])
        self.assertIsNone(self.service.find_earliest_date(state, Decimal("120")))

    def test_returns_none_when_no_date_in_horizon_is_safe(self):
        self.assertIsNone(self.service.find_earliest_date(self.state(), Decimal("81")))

    def test_rejects_non_decimal_or_negative_requested_amounts(self):
        with self.assertRaises(TypeError):
            self.service.find_earliest_date(self.state(), 80)
        with self.assertRaises(ValueError):
            self.service.find_earliest_date(self.state(), Decimal("-1"))


if __name__ == "__main__":
    unittest.main()
