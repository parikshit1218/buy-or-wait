"""Unit tests for PlanRanker."""

import pytest
from datetime import date
from decimal import Decimal
from candidate_plan_service import CandidatePlan
from forecast_engine import ProposedPayment, SpendingChange
from plan_ranker import PlanRanker


def test_plan_ranking_hierarchy():
    ranker = PlanRanker()
    deadline = date(2025, 2, 1)

    plan_completes_on_time = CandidatePlan(
        method="installments",
        affordability_status="affordable_with_plan",
        payment_plan_str="2025-01-10:100|2025-01-25:100",
        payments=(ProposedPayment(date(2025, 1, 10), Decimal("100")), ProposedPayment(date(2025, 1, 25), Decimal("100"))),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("200"),
        completion_date=date(2025, 1, 25),
        first_payment_date=date(2025, 1, 10),
        payment_count=2,
        payment_option_id="opt_1",
        completes_by_deadline=True,
        is_safe=True,
    )

    plan_misses_deadline = CandidatePlan(
        method="wait",
        affordability_status="affordable_later",
        payment_plan_str="2025-02-15:200",
        payments=(ProposedPayment(date(2025, 2, 15), Decimal("200")),),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("200"),
        completion_date=date(2025, 2, 15),
        first_payment_date=date(2025, 2, 15),
        payment_count=1,
        payment_option_id=None,
        completes_by_deadline=False,
        is_safe=True,
    )

    best = ranker.select_best_plan([plan_misses_deadline, plan_completes_on_time], deadline)
    assert best == plan_completes_on_time

