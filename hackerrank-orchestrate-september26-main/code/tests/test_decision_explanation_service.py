"""Unit tests for DecisionExplanationService."""

import pytest
from datetime import date
from decimal import Decimal
from candidate_plan_service import CandidatePlan
from decision_explanation_service import DecisionExplanationService
from financial_state_service import FinancialState
from forecast_engine import ProposedPayment, SpendingChange
from models import FinancialEvent, FinancialRequest


@pytest.fixture
def base_request() -> FinancialRequest:
    return FinancialRequest(
        request_id="req_01",
        user_id="user_01",
        request_date=date(2024, 3, 3),
        request_type="purchase",
        requested_amount=Decimal("25256"),
        desired_completion_date=date(2024, 3, 20),
        allows_partial_payment=True,
        request_text="Can I buy this?",
    )


@pytest.fixture
def base_state() -> FinancialState:
    events = (
        FinancialEvent(
            event_id="ev_01",
            user_id="user_01",
            event_type="subscription",
            description="Streaming Plan",
            category="entertainment",
            direction="debit",
            amount=Decimal("200"),
            currency="ZAR",
            event_date=date(2024, 2, 5),
            settlement_date=date(2024, 2, 5),
            status="settled",
            linked_event_id=None,
            flexibility="flexible",
            minimum_allowed_amount=Decimal("100"),
        ),
        FinancialEvent(
            event_id="ev_02",
            user_id="user_01",
            event_type="subscription",
            description="Gym Membership",
            category="health",
            direction="debit",
            amount=Decimal("500"),
            currency="ZAR",
            event_date=date(2024, 2, 10),
            settlement_date=date(2024, 2, 10),
            status="settled",
            linked_event_id=None,
            flexibility="flexible",
            minimum_allowed_amount=Decimal("250"),
        ),
    )
    return FinancialState(
        request_id="req_01",
        user_id="user_01",
        request_date=date(2024, 3, 3),
        home_currency="ZAR",
        available_balance=Decimal("58481.1"),
        minimum_balance_to_keep=Decimal("18000"),
        events=events,
        recurring_expenses=events,
        one_time_expenses=(),
        confirmed_income=(),
        confirmed_future_payments=(),
        refunds=(),
        transfers=(),
    )


def test_decision_explanation_full_payment_no_changes(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="full_payment",
        affordability_status="affordable_now",
        payment_plan_str="2024-03-03:25256",
        payments=(ProposedPayment(date(2024, 3, 3), Decimal("25256")),),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("25256"),
        completion_date=date(2024, 3, 3),
        first_payment_date=date(2024, 3, 3),
        payment_count=1,
        payment_option_id=None,
        completes_by_deadline=True,
        is_safe=True,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("25256"),
        earliest_full_payment_date=date(2024, 3, 3),
    )

    assert "Pay ZAR 25,256 today." in explanation
    assert "ZAR 18,000" in explanation
    assert "over the next 90 days" in explanation


def test_decision_explanation_full_payment_with_spending_changes(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="full_payment",
        affordability_status="affordable_with_plan",
        payment_plan_str="2024-03-03:25256",
        payments=(ProposedPayment(date(2024, 3, 3), Decimal("25256")),),
        spending_changes=(
            SpendingChange(event_id="ev_01", action_type="stop"),
            SpendingChange(event_id="ev_02", action_type="reduce_to", target_amount=Decimal("250")),
        ),
        spending_changes_str="stop:ev_01|reduce_to:ev_02:250",
        total_payable_amount=Decimal("25256"),
        completion_date=date(2024, 3, 3),
        first_payment_date=date(2024, 3, 3),
        payment_count=1,
        payment_option_id=None,
        completes_by_deadline=True,
        is_safe=True,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("25256"),
        earliest_full_payment_date=date(2024, 3, 3),
    )

    assert "Stop the streaming plan and reduce the gym membership to ZAR 250" in explanation
    assert "pay ZAR 25,256 today" in explanation
    assert "ZAR 18,000 available" in explanation


def test_decision_explanation_installments(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="installments",
        affordability_status="affordable_with_plan",
        payment_plan_str="2024-03-08:8500|2024-04-08:8500|2024-05-08:8500",
        payments=(
            ProposedPayment(date(2024, 3, 8), Decimal("8500")),
            ProposedPayment(date(2024, 4, 8), Decimal("8500")),
            ProposedPayment(date(2024, 5, 8), Decimal("8500")),
        ),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("25500"),
        completion_date=date(2024, 5, 8),
        first_payment_date=date(2024, 3, 8),
        payment_count=3,
        payment_option_id="opt_01",
        completes_by_deadline=True,
        is_safe=True,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("8500"),
        earliest_full_payment_date=date(2024, 4, 15),
    )

    assert "Use 3 installments of ZAR 8,500, starting 8 March 2024." in explanation
    assert "ZAR 18,000 available" in explanation


def test_decision_explanation_partial_payment(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="partial_payment",
        affordability_status="affordable_with_plan",
        payment_plan_str="2024-03-03:15000|2024-03-15:10256",
        payments=(
            ProposedPayment(date(2024, 3, 3), Decimal("15000")),
            ProposedPayment(date(2024, 3, 15), Decimal("10256")),
        ),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("25256"),
        completion_date=date(2024, 3, 15),
        first_payment_date=date(2024, 3, 3),
        payment_count=2,
        payment_option_id=None,
        completes_by_deadline=True,
        is_safe=True,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("15000"),
        earliest_full_payment_date=date(2024, 3, 15),
    )

    assert "Pay ZAR 15,000 today and the remaining ZAR 10,256 on 15 March 2024." in explanation
    assert "keeps the ZAR 18,000 minimum protected." in explanation


def test_decision_explanation_wait(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="wait",
        affordability_status="affordable_later",
        payment_plan_str="2024-03-15:25256",
        payments=(ProposedPayment(date(2024, 3, 15), Decimal("25256")),),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("25256"),
        completion_date=date(2024, 3, 15),
        first_payment_date=date(2024, 3, 15),
        payment_count=1,
        payment_option_id=None,
        completes_by_deadline=True,
        is_safe=True,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("5000"),
        earliest_full_payment_date=date(2024, 3, 15),
    )

    assert "Pay ZAR 25,256 in full on 15 March 2024." in explanation
    assert "below the ZAR 18,000 minimum" in explanation


def test_decision_explanation_not_recommended_with_positive_safe_amount(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="not_recommended",
        affordability_status="not_affordable",
        payment_plan_str="none",
        payments=(),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("0"),
        completion_date=None,
        first_payment_date=None,
        payment_count=0,
        payment_option_id=None,
        completes_by_deadline=False,
        is_safe=False,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("5000"),
        earliest_full_payment_date=None,
    )

    assert "Do not proceed with the ZAR 25,256 request." in explanation
    assert "Although ZAR 5,000 is available today" in explanation
    assert "cannot be completed safely within 90 days." in explanation


def test_decision_explanation_not_recommended_by_deadline(base_request, base_state):
    service = DecisionExplanationService()
    plan = CandidatePlan(
        method="not_recommended",
        affordability_status="not_affordable",
        payment_plan_str="none",
        payments=(),
        spending_changes=(),
        spending_changes_str="none",
        total_payable_amount=Decimal("0"),
        completion_date=None,
        first_payment_date=None,
        payment_count=0,
        payment_option_id=None,
        completes_by_deadline=False,
        is_safe=False,
    )

    explanation = service.generate_explanation(
        request=base_request,
        state=base_state,
        plan=plan,
        amount_safe_to_pay=Decimal("0"),
        earliest_full_payment_date=date(2024, 4, 15),  # Beyond desired completion date 2024-03-20
    )

    assert "Do not make this payment by 20 March 2024." in explanation
    assert "None of the available options keeps the ZAR 18,000 minimum protected." in explanation


