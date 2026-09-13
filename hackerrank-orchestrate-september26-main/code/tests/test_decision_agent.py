"""Unit tests for DecisionAgent end-to-end evaluation."""

import pytest
from datetime import date
from decimal import Decimal
from config import DEFAULT_DATASET_DIR
from decision_agent import DecisionAgent
from models import FinancialRequest


def test_decision_agent_sample_01():
    agent = DecisionAgent(DEFAULT_DATASET_DIR)
    req = FinancialRequest(
        request_id="request_01",
        user_id="user_01",
        request_date=date(2024, 3, 3),
        request_type="purchase",
        requested_amount=Decimal("25256"),
        desired_completion_date=date(2024, 3, 20),
        allows_partial_payment=True,
        request_text="Would paying for the laptop today leave enough for my regular expenses?",
    )

    out = agent.evaluate_request(req)
    assert out.request_id == "request_01"
    assert out.amount_safe_to_pay > Decimal("0")
    assert out.affordability_status in ("affordable_now", "affordable_with_plan")
    assert out.payment_plan != "none"

