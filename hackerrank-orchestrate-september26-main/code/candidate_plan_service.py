"""Candidate payment plan generation for Buy or Wait? financial decision agent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from financial_state_service import FinancialState
from forecast_engine import ForecastEngine, ProposedPayment, SpendingChange
from models import FinancialProfile, FinancialRequest, PaymentOption
from spending_change_service import SpendingChangeService


ZERO = Decimal("0")


@dataclass(frozen=True)
class CandidatePlan:
    """A fully specified candidate payment plan evaluated for safety."""

    method: str  # "full_payment", "partial_payment", "installments", "wait", "not_recommended"
    affordability_status: str  # "affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"
    payment_plan_str: str  # e.g. "2024-03-03:25256" or "none"
    payments: tuple[ProposedPayment, ...]
    spending_changes: tuple[SpendingChange, ...]
    spending_changes_str: str  # e.g. "none" or "stop:event_1|reduce_to:event_2:50"
    total_payable_amount: Decimal
    completion_date: date | None
    first_payment_date: date | None
    payment_count: int
    payment_option_id: str | None
    completes_by_deadline: bool
    is_safe: bool


class CandidatePlanService:
    """Generates and evaluates candidate plans across all supported modalities."""

    def __init__(
        self,
        forecast_engine: ForecastEngine | None = None,
        spending_service: SpendingChangeService | None = None,
    ) -> None:
        self._forecast_engine = forecast_engine or ForecastEngine()
        self._spending_service = spending_service or SpendingChangeService()

    def generate_candidate_plans(
        self,
        request: FinancialRequest,
        profile: FinancialProfile,
        state: FinancialState,
        payment_options: Sequence[PaymentOption],
        amount_safe_to_pay: Decimal,
        earliest_full_payment_date: date | None,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> list[CandidatePlan]:
        """Generate all eligible candidate plans and verify their 90-day safety."""
        allowed_methods = set(profile.payment_methods_user_will_consider)
        flexible_options = self._spending_service.get_flexible_options(profile, state)
        change_combinations = self._spending_service.generate_change_combinations(flexible_options)

        candidates: list[CandidatePlan] = []

        # 1. Full Payment candidates (with 0 or more spending changes)
        if "full_payment" in allowed_methods:
            full_payment = (ProposedPayment(payment_date=request.request_date, amount=request.requested_amount),)
            plan_str = f"{request.request_date.isoformat()}:{request.requested_amount}"

            for changes in change_combinations:
                result = self._forecast_engine.forecast(
                    state=state,
                    proposed_payment_plan=full_payment,
                    spending_changes=changes,
                    user_messages=user_messages,
                )
                if result.safe:
                    changes_str = self._format_spending_changes(changes)
                    status = "affordable_now" if not changes else "affordable_with_plan"
                    candidates.append(
                        CandidatePlan(
                            method="full_payment",
                            affordability_status=status,
                            payment_plan_str=plan_str,
                            payments=full_payment,
                            spending_changes=changes,
                            spending_changes_str=changes_str,
                            total_payable_amount=request.requested_amount,
                            completion_date=request.request_date,
                            first_payment_date=request.request_date,
                            payment_count=1,
                            payment_option_id=None,
                            completes_by_deadline=request.request_date <= request.desired_completion_date,
                            is_safe=True,
                        )
                    )

        # 2. Installment candidates from supplied payment options
        if "installments" in allowed_methods:
            req_options = [
                o for o in payment_options
                if o.request_id == request.request_id and o.payment_method == "installments" and o.number_of_payments > 1
            ]
            for opt in req_options:
                # Check max installment months constraint if specified
                if profile.max_installment_months is not None:
                    # Duration in months approximation based on number of payments
                    if opt.number_of_payments > profile.max_installment_months:
                        continue

                # Build payment schedule
                payments_list: list[ProposedPayment] = []
                freq = opt.payment_frequency_days or 30
                for i in range(opt.number_of_payments):
                    p_date = opt.first_payment_date + timedelta(days=i * freq)
                    payments_list.append(ProposedPayment(payment_date=p_date, amount=opt.payment_amount))
                
                inst_payments = tuple(payments_list)
                plan_str = "|".join(f"{p.payment_date.isoformat()}:{p.amount}" for p in inst_payments)
                completion_date = inst_payments[-1].payment_date
                completes_by_deadline = completion_date <= request.desired_completion_date

                for changes in change_combinations:
                    result = self._forecast_engine.forecast(
                        state=state,
                        proposed_payment_plan=inst_payments,
                        spending_changes=changes,
                        user_messages=user_messages,
                    )
                    if result.safe:
                        changes_str = self._format_spending_changes(changes)
                        candidates.append(
                            CandidatePlan(
                                method="installments",
                                affordability_status="affordable_with_plan",
                                payment_plan_str=plan_str,
                                payments=inst_payments,
                                spending_changes=changes,
                                spending_changes_str=changes_str,
                                total_payable_amount=opt.total_payable_amount,
                                completion_date=completion_date,
                                first_payment_date=opt.first_payment_date,
                                payment_count=opt.number_of_payments,
                                payment_option_id=opt.payment_option_id,
                                completes_by_deadline=completes_by_deadline,
                                is_safe=True,
                            )
                        )

        # 3. Partial Payment candidate
        if (
            request.allows_partial_payment
            and "partial_payment" in allowed_methods
            and ZERO < amount_safe_to_pay < request.requested_amount
            and earliest_full_payment_date is not None
            and earliest_full_payment_date <= request.desired_completion_date
        ):
            remaining_amount = request.requested_amount - amount_safe_to_pay
            partial_payments = (
                ProposedPayment(payment_date=request.request_date, amount=amount_safe_to_pay),
                ProposedPayment(payment_date=earliest_full_payment_date, amount=remaining_amount),
            )
            plan_str = (
                f"{request.request_date.isoformat()}:{amount_safe_to_pay}|"
                f"{earliest_full_payment_date.isoformat()}:{remaining_amount}"
            )
            # Verify safety of the 2-payment partial plan
            result = self._forecast_engine.forecast(
                state=state,
                proposed_payment_plan=partial_payments,
                spending_changes=(),
                user_messages=user_messages,
            )
            if result.safe:
                candidates.append(
                    CandidatePlan(
                        method="partial_payment",
                        affordability_status="affordable_with_plan",
                        payment_plan_str=plan_str,
                        payments=partial_payments,
                        spending_changes=(),
                        spending_changes_str="none",
                        total_payable_amount=request.requested_amount,
                        completion_date=earliest_full_payment_date,
                        first_payment_date=request.request_date,
                        payment_count=2,
                        payment_option_id=None,
                        completes_by_deadline=True,
                        is_safe=True,
                    )
                )

        # 4. Wait candidate (single full payment at earliest_full_payment_date)
        if "full_payment" in allowed_methods and earliest_full_payment_date is not None:
            wait_payments = (ProposedPayment(payment_date=earliest_full_payment_date, amount=request.requested_amount),)
            plan_str = f"{earliest_full_payment_date.isoformat()}:{request.requested_amount}"
            completes_by_deadline = earliest_full_payment_date <= request.desired_completion_date
            candidates.append(
                CandidatePlan(
                    method="wait",
                    affordability_status="affordable_later",
                    payment_plan_str=plan_str,
                    payments=wait_payments,
                    spending_changes=(),
                    spending_changes_str="none",
                    total_payable_amount=request.requested_amount,
                    completion_date=earliest_full_payment_date,
                    first_payment_date=earliest_full_payment_date,
                    payment_count=1,
                    payment_option_id=None,
                    completes_by_deadline=completes_by_deadline,
                    is_safe=True,
                )
            )

        # 5. Fallback: Not Recommended
        candidates.append(
            CandidatePlan(
                method="not_recommended",
                affordability_status="not_affordable",
                payment_plan_str="none",
                payments=(),
                spending_changes=(),
                spending_changes_str="none",
                total_payable_amount=Decimal("999999999999"),
                completion_date=None,
                first_payment_date=None,
                payment_count=0,
                payment_option_id=None,
                completes_by_deadline=False,
                is_safe=False,
            )
        )

        return candidates

    @staticmethod
    def _format_spending_changes(changes: tuple[SpendingChange, ...]) -> str:
        if not changes:
            return "none"
        return "|".join(c.to_str() for c in changes)

