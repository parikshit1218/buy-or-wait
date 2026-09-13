"""Comprehensive unit tests for CandidatePlanService and PlanRanker."""

import sys
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_plan_service import CandidatePlan, CandidatePlanService
from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment, SpendingChange
from models import FinancialProfile, FinancialRequest, PaymentOption
from plan_ranker import PlanRanker
from spending_change_service import SpendingChangeService


class CandidatePlanServiceTests(unittest.TestCase):
    def setUp(self):
        self.forecast_engine = ForecastEngine()
        self.spending_service = SpendingChangeService()
        self.service = CandidatePlanService(self.forecast_engine, self.spending_service)
        self.ranker = PlanRanker()
        self.request_date = date(2026, 1, 10)
        self.completion_date = date(2026, 2, 10)

    def profile(self, methods=("full_payment", "partial_payment", "installments"), max_months=3):
        return FinancialProfile(
            user_id="u1",
            home_currency="USD",
            current_available_balance=Decimal("1000"),
            minimum_balance_to_keep=Decimal("200"),
            financial_priorities=("savings",),
            expense_categories_to_protect=(),
            expense_categories_user_is_willing_to_reduce=(),
            expense_categories_user_is_willing_to_stop=(),
            payment_methods_user_will_consider=methods,
            max_installment_months=max_months,
        )

    def request(self, allows_partial=True, amount="500", deadline=None):
        return FinancialRequest(
            request_id="r1",
            user_id="u1",
            request_date=self.request_date,
            request_type="purchase",
            requested_amount=Decimal(amount),
            desired_completion_date=deadline or self.completion_date,
            allows_partial_payment=allows_partial,
            request_text="Can I buy this?",
        )

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
            confirmed_income=(),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    def test_full_payment_candidate_generated_when_allowed_and_safe(self):
        req = self.request()
        prof = self.profile()
        st = self.state()
        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("500"),
            earliest_full_payment_date=self.request_date,
        )

        methods = [c.method for c in candidates if c.is_safe]
        self.assertIn("full_payment", methods)

    def test_full_payment_excluded_when_not_in_user_preferences(self):
        req = self.request()
        prof = self.profile(methods=("installments",))  # No full_payment
        st = self.state()
        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("500"),
            earliest_full_payment_date=self.request_date,
        )

        methods = [c.method for c in candidates if c.is_safe]
        self.assertNotIn("full_payment", methods)

    def test_partial_payment_only_generated_when_allowed_and_partial_safe(self):
        req = self.request(allows_partial=True)
        prof = self.profile()
        st = self.state()
        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("200"),  # 0 < 200 < 500
            earliest_full_payment_date=self.request_date + timedelta(days=15),
        )

        methods = [c.method for c in candidates if c.is_safe]
        self.assertIn("partial_payment", methods)

    def test_partial_payment_rejected_when_request_disallows_partial(self):
        req = self.request(allows_partial=False)
        prof = self.profile()
        st = self.state()
        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("200"),
            earliest_full_payment_date=self.request_date + timedelta(days=15),
        )

        methods = [c.method for c in candidates if c.is_safe]
        self.assertNotIn("partial_payment", methods)

    def test_installments_respects_max_installment_months(self):
        req = self.request()
        prof = self.profile(max_months=3)
        st = self.state()

        opt_3m = PaymentOption(
            payment_option_id="opt_3m",
            request_id="r1",
            payment_method="installments",
            payment_amount=Decimal("170"),
            number_of_payments=3,
            first_payment_date=self.request_date,
            payment_frequency_days=30,
            financing_fee=Decimal("10"),
            total_payable_amount=Decimal("510"),
        )
        opt_6m = PaymentOption(
            payment_option_id="opt_6m",
            request_id="r1",
            payment_method="installments",
            payment_amount=Decimal("90"),
            number_of_payments=6,
            first_payment_date=self.request_date,
            payment_frequency_days=30,
            financing_fee=Decimal("40"),
            total_payable_amount=Decimal("540"),
        )

        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(opt_3m, opt_6m),
            amount_safe_to_pay=Decimal("500"),
            earliest_full_payment_date=self.request_date,
        )

        opt_ids = [c.payment_option_id for c in candidates if c.method == "installments"]
        self.assertIn("opt_3m", opt_ids)
        self.assertNotIn("opt_6m", opt_ids)

    def test_plan_ranking_exact_hierarchy(self):
        # 1. On-time vs late
        on_time = CandidatePlan(
            method="installments",
            affordability_status="affordable_with_plan",
            payment_plan_str="plan_1",
            payments=(),
            spending_changes=(),
            spending_changes_str="none",
            total_payable_amount=Decimal("100"),
            completion_date=self.request_date + timedelta(days=10),
            first_payment_date=self.request_date,
            payment_count=2,
            payment_option_id="opt_1",
            completes_by_deadline=True,
            is_safe=True,
        )
        late = CandidatePlan(
            method="wait",
            affordability_status="affordable_later",
            payment_plan_str="plan_2",
            payments=(),
            spending_changes=(),
            spending_changes_str="none",
            total_payable_amount=Decimal("100"),
            completion_date=self.request_date + timedelta(days=40),
            first_payment_date=self.request_date + timedelta(days=40),
            payment_count=1,
            payment_option_id=None,
            completes_by_deadline=False,
            is_safe=True,
        )
        best = self.ranker.select_best_plan([late, on_time], self.completion_date)
        self.assertEqual("installments", best.method)

        # 2. No spending changes vs spending changes
        with_change = CandidatePlan(
            method="full_payment",
            affordability_status="affordable_with_plan",
            payment_plan_str="plan_3",
            payments=(),
            spending_changes=(SpendingChange("stop", "e1"),),
            spending_changes_str="stop:e1",
            total_payable_amount=Decimal("100"),
            completion_date=self.request_date,
            first_payment_date=self.request_date,
            payment_count=1,
            payment_option_id=None,
            completes_by_deadline=True,
            is_safe=True,
        )
        best2 = self.ranker.select_best_plan([with_change, on_time], self.completion_date)
        self.assertEqual("installments", best2.method)

        # 3. Minimize total payable amount
        expensive_on_time = CandidatePlan(
            method="installments",
            affordability_status="affordable_with_plan",
            payment_plan_str="plan_exp",
            payments=(),
            spending_changes=(),
            spending_changes_str="none",
            total_payable_amount=Decimal("150"),
            completion_date=self.request_date + timedelta(days=10),
            first_payment_date=self.request_date,
            payment_count=2,
            payment_option_id="opt_2",
            completes_by_deadline=True,
            is_safe=True,
        )
        best3 = self.ranker.select_best_plan([expensive_on_time, on_time], self.completion_date)
        self.assertEqual("opt_1", best3.payment_option_id)

    def test_fallback_to_not_recommended_when_all_unsafe(self):
        req = self.request()
        prof = self.profile()
        # Balance = 0, Min = 200 -> completely unsafe
        st = self.state(balance="0", minimum="200")
        candidates = self.service.generate_candidate_plans(
            request=req,
            profile=prof,
            state=st,
            payment_options=(),
            amount_safe_to_pay=Decimal("0"),
            earliest_full_payment_date=None,
        )

        best = self.ranker.select_best_plan(candidates, self.completion_date)
        self.assertEqual("not_recommended", best.method)
        self.assertEqual("not_affordable", best.affordability_status)
        self.assertEqual("none", best.payment_plan_str)


if __name__ == "__main__":
    unittest.main()

