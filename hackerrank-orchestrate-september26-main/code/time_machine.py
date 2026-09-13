"""Financial Time Machine: Interactive scenario simulation and what-if analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from earliest_full_payment_service import EarliestFullPaymentService
from financial_state_service import FinancialState
from forecast_engine import ForecastEngine, ForecastResult, ProposedPayment
from models import FinancialProfile, FinancialRequest, PaymentOption
from safe_now_calculator import SafeNowCalculator


ZERO = Decimal("0")


@dataclass(frozen=True)
class ScenarioResult:
    """Outcome metrics for a simulated financial decision scenario."""

    scenario_name: str  # "BUY_NOW", "WAIT", "PARTIAL_PAYMENT", "INSTALLMENTS_<option_id>"
    is_safe: bool
    lowest_balance: Decimal
    lowest_balance_date: date
    safety_margin: Decimal
    completion_date: date | None
    total_amount_paid: Decimal
    number_of_payments: int
    payments: tuple[ProposedPayment, ...]


class FinancialTimeMachine:
    """Simulates prospective purchase scenarios using the deterministic 90-day ForecastEngine."""

    def __init__(
        self,
        forecast_engine: ForecastEngine | None = None,
        safe_now_calculator: SafeNowCalculator | None = None,
        earliest_service: EarliestFullPaymentService | None = None,
    ) -> None:
        self._forecast_engine = forecast_engine or ForecastEngine()
        self._safe_now_calculator = safe_now_calculator or SafeNowCalculator(self._forecast_engine)
        self._earliest_service = earliest_service or EarliestFullPaymentService(self._forecast_engine)

    def simulate_all_scenarios(
        self,
        request: FinancialRequest,
        profile: FinancialProfile,
        state: FinancialState,
        payment_options: Sequence[PaymentOption] = (),
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> list[ScenarioResult]:
        """Run forward 90-day what-if simulations for all major prospective decisions."""
        scenarios: list[ScenarioResult] = []

        # 1. BUY_NOW scenario (100% upfront on request_date)
        scenarios.append(
            self.simulate_buy_now(request, state, user_messages)
        )

        # Pre-compute earliest safe date and safe-now amount for dependent scenarios
        earliest_date = self._earliest_service.find_earliest_date(
            state=state,
            requested_amount=request.requested_amount,
            user_messages=user_messages,
        )
        safe_now = self._safe_now_calculator.calculate_safe_amount(
            state=state,
            requested_amount=request.requested_amount,
            user_messages=user_messages,
        )


        # 2. WAIT scenario (Full payment deferred to earliest safe full-payment date)
        scenarios.append(
            self.simulate_wait(request, state, earliest_date, user_messages)
        )

        # 3. PARTIAL_PAYMENT scenario (Pay safe_now today, remainder at earliest safe date)
        scenarios.append(
            self.simulate_partial_payment(request, state, safe_now, earliest_date, user_messages)
        )

        # 4. INSTALLMENT scenarios (Simulate each valid option provided in dataset)
        req_options = [
            opt for opt in payment_options
            if opt.request_id == request.request_id
            and opt.payment_method == "installments"
            and opt.number_of_payments > 1
        ]
        for opt in req_options:
            scenarios.append(
                self.simulate_installment_option(opt, state, user_messages)
            )

        return scenarios

    def simulate_buy_now(
        self,
        request: FinancialRequest,
        state: FinancialState,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ScenarioResult:
        """Simulate paying 100% on request_date with no spending changes."""
        payments = (ProposedPayment(payment_date=request.request_date, amount=request.requested_amount),)
        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=payments,
            spending_changes=(),
            user_messages=user_messages,
        )
        return ScenarioResult(
            scenario_name="BUY_NOW",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            completion_date=request.request_date,
            total_amount_paid=request.requested_amount,
            number_of_payments=1,
            payments=payments,
        )

    def simulate_wait(
        self,
        request: FinancialRequest,
        state: FinancialState,
        wait_date: date | None = None,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ScenarioResult:
        """Simulate deferring full payment to a future date."""
        target_date = wait_date or (request.request_date + timedelta(days=30))
        payments = (ProposedPayment(payment_date=target_date, amount=request.requested_amount),)
        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=payments,
            spending_changes=(),
            user_messages=user_messages,
        )
        return ScenarioResult(
            scenario_name="WAIT",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            completion_date=target_date,
            total_amount_paid=request.requested_amount,
            number_of_payments=1,
            payments=payments,
        )

    def simulate_partial_payment(
        self,
        request: FinancialRequest,
        state: FinancialState,
        amount_safe_to_pay: Decimal,
        second_payment_date: date | None = None,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ScenarioResult:
        """Simulate a 2-stage split payment."""
        target_second_date = second_payment_date or (request.request_date + timedelta(days=30))
        remaining = max(ZERO, request.requested_amount - amount_safe_to_pay)
        payments = (
            ProposedPayment(payment_date=request.request_date, amount=amount_safe_to_pay),
            ProposedPayment(payment_date=target_second_date, amount=remaining),
        )
        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=payments,
            spending_changes=(),
            user_messages=user_messages,
        )
        return ScenarioResult(
            scenario_name="PARTIAL_PAYMENT",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            completion_date=target_second_date,
            total_amount_paid=request.requested_amount,
            number_of_payments=2,
            payments=payments,
        )

    def simulate_installment_option(
        self,
        option: PaymentOption,
        state: FinancialState,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ScenarioResult:
        """Simulate a specific installment payment schedule."""
        freq = option.payment_frequency_days or 30
        payments_list: list[ProposedPayment] = []
        for i in range(option.number_of_payments):
            p_date = option.first_payment_date + timedelta(days=i * freq)
            payments_list.append(ProposedPayment(payment_date=p_date, amount=option.payment_amount))

        payments = tuple(payments_list)
        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=payments,
            spending_changes=(),
            user_messages=user_messages,
        )
        completion_date = payments[-1].payment_date
        return ScenarioResult(
            scenario_name=f"INSTALLMENTS_{option.payment_option_id}",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            completion_date=completion_date,
            total_amount_paid=option.total_payable_amount,
            number_of_payments=option.number_of_payments,
            payments=payments,
        )
