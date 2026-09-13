"""End-to-end financial decision engine orchestrating state, forecast, ranking, and explanation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Mapping, Sequence

from candidate_plan_service import CandidatePlan, CandidatePlanService
from data_loader import DataLoader
from decision_explanation_service import DecisionExplanationService
from earliest_full_payment_service import EarliestFullPaymentService
from financial_state_service import FinancialState, FinancialStateService
from forecast_engine import ForecastEngine
from models import FinancialProfile, FinancialRequest, OutputRow, PaymentOption
from plan_ranker import PlanRanker
from safe_now_calculator import SafeNowCalculator
from spending_change_service import SpendingChangeService


ZERO = Decimal("0")


class DecisionAgent:
    """Autonomous financial decision agent for the Buy or Wait? challenge."""

    def __init__(self, dataset_dir: str | Path) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.loader = DataLoader(self.dataset_dir)
        self.loader.load_all()

        self.state_service = FinancialStateService(self.dataset_dir)
        self.forecast_engine = ForecastEngine()
        self.safe_now_calculator = SafeNowCalculator(self.forecast_engine)
        self.earliest_service = EarliestFullPaymentService(self.forecast_engine)
        self.spending_service = SpendingChangeService()
        self.plan_service = CandidatePlanService(self.forecast_engine, self.spending_service)
        self.ranker = PlanRanker()
        self.explanation_service = DecisionExplanationService()

        # Indexes
        self._profiles = {p.user_id: p for p in self.loader.load_profiles()}
        self._payment_options = self.loader.load_payment_options()
        self._messages = self.loader.load_messages()
        self._messages_by_user: dict[str, list[Mapping[str, str]]] = {}
        for m in self._messages:
            self._messages_by_user.setdefault(m.user_id, []).append(m.__dict__)

    def evaluate_request(self, request: FinancialRequest) -> OutputRow:
        """Evaluate a single financial request and produce the conforming OutputRow."""
        profile = self._profiles.get(request.user_id)
        if profile is None:
            raise KeyError(f"No profile found for user_id: {request.user_id}")

        user_msgs = self._messages_by_user.get(request.user_id, [])
        state = self.state_service.reconstruct(request.request_id)

        # 1. Calculate amount_safe_to_pay today using SafeNowCalculator
        amount_safe_to_pay = self.safe_now_calculator.calculate_safe_amount(
            state=state,
            requested_amount=request.requested_amount,
            user_messages=user_msgs,
        )

        # 3. Calculate earliest safe date for full payment
        if amount_safe_to_pay == request.requested_amount:
            earliest_full_date: date | None = request.request_date
        else:
            earliest_full_date = self.earliest_service.find_earliest_date(
                state=state,
                requested_amount=request.requested_amount,
                spending_changes=(),
                user_messages=user_msgs,
            )

        # 4. Generate candidate plans
        candidates = self.plan_service.generate_candidate_plans(
            request=request,
            profile=profile,
            state=state,
            payment_options=self._payment_options,
            amount_safe_to_pay=amount_safe_to_pay,
            earliest_full_payment_date=earliest_full_date,
            user_messages=user_msgs,
        )

        # 5. Select optimal candidate plan via multi-criteria ranking
        best_plan = self.ranker.select_best_plan(
            candidates=candidates,
            desired_completion_date=request.desired_completion_date,
        )

        # 6. Generate decision explanation
        explanation = self.explanation_service.generate_explanation(
            request=request,
            state=state,
            plan=best_plan,
            amount_safe_to_pay=amount_safe_to_pay,
            earliest_full_payment_date=earliest_full_date,
        )

        # For not_recommended / not_affordable, earliest date should be None in output per spec
        output_earliest_date = earliest_full_date
        if best_plan.method == "not_recommended" and best_plan.affordability_status == "not_affordable":
            # If not affordable within 90 days, leave empty
            output_earliest_date = earliest_full_date if (earliest_full_date and earliest_full_date <= request.request_date + date.resolution * 90) else None

        return OutputRow(
            request_id=request.request_id,
            amount_safe_to_pay=amount_safe_to_pay,
            affordability_status=best_plan.affordability_status,
            recommended_payment_method=best_plan.method,
            payment_plan=best_plan.payment_plan_str,
            earliest_date_for_full_payment=output_earliest_date if best_plan.affordability_status != "not_affordable" else None,
            spending_changes_needed=best_plan.spending_changes_str,
            decision_explanation=explanation,
        )

