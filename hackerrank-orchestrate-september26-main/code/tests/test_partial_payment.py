"""Comprehensive tests for partial-payment behavior and requirements.

Requirements:
- request must allow partial payment
- user must accept partial_payment
- amount_safe_to_pay > 0
- amount_safe_to_pay < requested_amount
- earliest full-payment date <= desired_completion_date

Plan structure:
- request_date : amount_safe_to_pay
- earliest_date_for_full_payment : remaining_amount
- The two payments must add exactly to requested_amount.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_plan_service import CandidatePlan, CandidatePlanService
from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment
from models import FinancialProfile, FinancialRequest
from plan_ranker import PlanRanker
from spending_change_service import SpendingChangeService


class PartialPaymentBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.forecast_engine = ForecastEngine()
        self.spending_service = SpendingChangeService()
        self.service = CandidatePlanService(self.forecast_engine, self.spending_service)
        self.ranker = PlanRanker()
        self.request_date = date(2026, 3, 1)
        self.earliest_date = date(2026, 3, 15)
        self.desired_completion_date = date(2026, 3, 31)

    def make_profile(
        self,
        methods=("full_payment", "partial_payment", "installments"),
        balance="1000",
        minimum="200",
    ) -> FinancialProfile:
        return FinancialProfile(
            user_id="user_test",
            home_currency="USD",
            current_available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            financial_priorities=("emergency_savings",),
            expense_categories_to_protect=(),
            expense_categories_user_is_willing_to_reduce=(),
            expense_categories_user_is_willing_to_stop=(),
            payment_methods_user_will_consider=methods,
            max_installment_months=6,
        )

    def make_request(
        self,
        allows_partial: bool = True,
        amount: str = "500",
        deadline: date | None = None,
    ) -> FinancialRequest:
        return FinancialRequest(
            request_id="req_test",
            user_id="user_test",
            request_date=self.request_date,
            request_type="purchase",
            requested_amount=Decimal(amount),
            desired_completion_date=deadline or self.desired_completion_date,
            allows_partial_payment=allows_partial,
            request_text="Test purchase",
        )

    def make_event(
        self,
        event_id: str,
        *,
        day: date,
        amount: str,
        direction: str = "debit",
        meaning: str = "expense",
        status: str = "scheduled",
        income: bool = False,
    ) -> NormalizedEvent:
        return NormalizedEvent(
            event_id=event_id,
            user_id="user_test",
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
            status=status,
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None,
            financial_meaning=meaning,
            is_recurring=False,
            is_confirmed_income=income,
            is_confirmed_future_payment=direction == "debit" and status in {"pending", "scheduled"},
            is_refund=meaning == "refund",
            is_transfer=False,
            included_in_cash_state=True,
            exclusion_reason=None,
            evidence_resolution=None,
        )

    def make_state(self, balance="1000", minimum="200", events=()) -> FinancialState:
        items = tuple(events)
        return FinancialState(
            request_id="req_test",
            user_id="user_test",
            request_date=self.request_date,
            home_currency="USD",
            available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            events=items,
            recurring_expenses=(),
            one_time_expenses=tuple(e for e in items if not e.is_confirmed_income),
            confirmed_income=tuple(e for e in items if e.is_confirmed_income),
            confirmed_future_payments=tuple(e for e in items if e.is_confirmed_future_payment),
            refunds=(),
            transfers=(),
        )

    def test_partial_payment_generated_and_exact_structure(self):
        """Verify plan contains request_date:safe_now and earliest_date:remaining, summing to requested_amount."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("partial_payment", "wait"))
        # Income arrives on 2026-03-15 to fund the remaining payment
        salary = self.make_event("salary_1", day=self.earliest_date, amount="1000", direction="credit", meaning="income", income=True)
        st = self.make_state(balance="450", minimum="200", events=(salary,))
        safe_now = Decimal("250")  # 450 - 200 = 250

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=safe_now,
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 1)
        plan = partial_plans[0]

        # 1. Verification of payments
        self.assertEqual(plan.payment_count, 2)
        self.assertEqual(len(plan.payments), 2)
        p1, p2 = plan.payments

        self.assertEqual(p1.payment_date, self.request_date)
        self.assertEqual(p1.amount, safe_now)

        self.assertEqual(p2.payment_date, self.earliest_date)
        self.assertEqual(p2.amount, Decimal("250"))  # 500 - 250 = 250

        # Exact sum
        self.assertEqual(p1.amount + p2.amount, req.requested_amount)
        self.assertEqual(plan.total_payable_amount, req.requested_amount)

        # Plan string format
        expected_plan_str = f"{self.request_date.isoformat()}:250|{self.earliest_date.isoformat()}:250"
        self.assertEqual(plan.payment_plan_str, expected_plan_str)

        # Status and metadata
        self.assertEqual(plan.affordability_status, "affordable_with_plan")
        self.assertEqual(plan.spending_changes_str, "none")
        self.assertEqual(plan.completion_date, self.earliest_date)
        self.assertEqual(plan.first_payment_date, self.request_date)
        self.assertTrue(plan.completes_by_deadline)
        self.assertTrue(plan.is_safe)

    def test_rejected_when_request_disallows_partial(self):
        """Requirement: request must allow partial payment."""
        req = self.make_request(allows_partial=False, amount="500")
        prof = self.make_profile(methods=("partial_payment",))
        salary = self.make_event("salary_1", day=self.earliest_date, amount="1000", direction="credit", meaning="income", income=True)
        st = self.make_state(balance="450", minimum="200", events=(salary,))

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("250"),
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_rejected_when_user_does_not_consider_partial_payment(self):
        """Requirement: user must accept partial_payment."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("full_payment", "installments"))  # No partial_payment
        salary = self.make_event("salary_1", day=self.earliest_date, amount="1000", direction="credit", meaning="income", income=True)
        st = self.make_state(balance="450", minimum="200", events=(salary,))

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("250"),
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_rejected_when_amount_safe_to_pay_is_zero(self):
        """Requirement: amount_safe_to_pay > 0."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("partial_payment",))
        st = self.make_state(balance="200", minimum="200")

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("0"),
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_rejected_when_amount_safe_to_pay_equals_requested_amount(self):
        """Requirement: amount_safe_to_pay < requested_amount."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("partial_payment", "full_payment"))
        st = self.make_state(balance="1000", minimum="200")

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("500"),
            earliest_full_payment_date=self.request_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_rejected_when_earliest_full_payment_date_is_none(self):
        """Requirement: earliest full-payment date must exist."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("partial_payment",))
        st = self.make_state(balance="450", minimum="200")

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("250"),
            earliest_full_payment_date=None,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_rejected_when_earliest_full_payment_date_after_desired_completion(self):
        """Requirement: earliest full-payment date <= desired_completion_date."""
        req = self.make_request(
            allows_partial=True,
            amount="500",
            deadline=date(2026, 3, 10),  # before earliest_date (2026-03-15)
        )
        prof = self.make_profile(methods=("partial_payment",))
        salary = self.make_event("salary_1", day=self.earliest_date, amount="1000", direction="credit", meaning="income", income=True)
        st = self.make_state(balance="450", minimum="200", events=(salary,))

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("250"),
            earliest_full_payment_date=self.earliest_date,  # 2026-03-15 > 2026-03-10
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)

    def test_two_payments_sum_with_odd_decimals(self):
        """Validate decimal precision and exact sum for arbitrary decimal amounts."""
        req = self.make_request(allows_partial=True, amount="12345.67")
        prof = self.make_profile(methods=("partial_payment",))
        salary = self.make_event("salary_1", day=self.earliest_date, amount="20000", direction="credit", meaning="income", income=True)
        st = self.make_state(balance="20000", minimum="1000", events=(salary,))
        safe_now = Decimal("4321.89")

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=safe_now,
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 1)
        plan = partial_plans[0]

        p1, p2 = plan.payments
        self.assertEqual(p1.amount, Decimal("4321.89"))
        self.assertEqual(p2.amount, Decimal("8023.78"))
        self.assertEqual(p1.amount + p2.amount, Decimal("12345.67"))
        self.assertEqual(
            plan.payment_plan_str,
            f"{self.request_date.isoformat()}:4321.89|{self.earliest_date.isoformat()}:8023.78",
        )

    def test_rejected_if_second_payment_violates_future_minimum_balance(self):
        """If large subsequent expense makes second payment unsafe, plan must be rejected."""
        req = self.make_request(allows_partial=True, amount="500")
        prof = self.make_profile(methods=("partial_payment",))
        # Salary is 300 on day 15, but rent of 250 also hits on day 15
        salary = self.make_event("salary_1", day=self.earliest_date, amount="300", direction="credit", meaning="income", income=True)
        rent = self.make_event("rent_1", day=self.earliest_date, amount="250", direction="debit", meaning="expense")
        # Balance = 450, Min = 200. Safe now = 250.
        # Day 0: 450 - 250 = 200.
        # Day 15: 200 + 300 (salary) - 250 (rent) - 250 (second payment) = 0 < 200 (violates minimum!)
        st = self.make_state(balance="450", minimum="200", events=(salary, rent))

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("250"),
            earliest_full_payment_date=self.earliest_date,
        )

        partial_plans = [c for c in candidates if c.method == "partial_payment"]
        self.assertEqual(len(partial_plans), 0)


if __name__ == "__main__":
    unittest.main()

