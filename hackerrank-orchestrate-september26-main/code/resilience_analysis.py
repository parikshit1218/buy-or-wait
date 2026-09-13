"""Resilience Analysis: Stress-testing approved financial plans under adverse cash flow shocks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Mapping, Sequence

from candidate_plan_service import CandidatePlan
from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ForecastResult, ProposedPayment, SpendingChange


ZERO = Decimal("0")


@dataclass(frozen=True)
class ResilienceScenarioResult:
    """Outcome of a single cash-flow stress test."""

    stress_test_name: str  # e.g. "SALARY_DELAY_3_DAYS", "SALARY_DELAY_7_DAYS", "UNEXPECTED_EXPENSE"
    is_safe: bool
    lowest_balance: Decimal
    lowest_balance_date: date
    safety_margin: Decimal
    description: str


@dataclass(frozen=True)
class ResilienceReport:
    """Comprehensive resilience stress-testing report for an approved plan."""

    label: str  # "RESILIENCE ANALYSIS"
    plan_description: str
    is_baseline_safe: bool
    baseline_safety_margin: Decimal
    stress_results: tuple[ResilienceScenarioResult, ...]


class ResilienceAnalyzer:
    """Performs non-destructive cash flow stress testing on prospective financial plans.

    CRITICAL INVARIANT:
    This is strictly an advisory/diagnostic analysis layer and must NEVER alter or override
    the official affordability decision or challenge output.
    """

    def __init__(self, forecast_engine: ForecastEngine | None = None) -> None:
        self._forecast_engine = forecast_engine or ForecastEngine()

    def analyze_plan_resilience(
        self,
        state: FinancialState,
        plan_payments: Sequence[ProposedPayment],
        spending_changes: Sequence[SpendingChange] = (),
        unexpected_expense_amount: Decimal | None = None,
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ResilienceReport:
        """Evaluate plan durability across salary delay (3d, 7d) and unexpected debit shocks."""
        # 1. Baseline evaluation
        baseline = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=plan_payments,
            spending_changes=spending_changes,
            user_messages=user_messages,
        )

        stress_results: list[ResilienceScenarioResult] = []

        # Find the primary expected salary day
        payroll_events = [
            e for e in state.events
            if e.event_type.lower() == "income"
            and e.included_in_cash_state
            and ("payroll" in e.description.lower() or "salary" in e.description.lower())
        ]
        next_salary_date = self._find_next_salary_date(state.request_date, payroll_events)

        # 2. Stress Test A: Salary Delayed by 3 Days
        stress_results.append(
            self._simulate_salary_delay(
                state=state,
                plan_payments=plan_payments,
                spending_changes=spending_changes,
                delay_days=3,
                base_salary_date=next_salary_date,
                user_messages=user_messages,
            )
        )

        # 3. Stress Test B: Salary Delayed by 7 Days
        stress_results.append(
            self._simulate_salary_delay(
                state=state,
                plan_payments=plan_payments,
                spending_changes=spending_changes,
                delay_days=7,
                base_salary_date=next_salary_date,
                user_messages=user_messages,
            )
        )

        # 4. Stress Test C: Unexpected Expense Shock
        # Default unexpected expense: 10% of starting balance or minimum $50
        exp_amt = unexpected_expense_amount
        if exp_amt is None:
            exp_amt = max(Decimal("50"), (state.available_balance * Decimal("0.10")).quantize(Decimal("0.01")))

        stress_results.append(
            self._simulate_unexpected_expense(
                state=state,
                plan_payments=plan_payments,
                spending_changes=spending_changes,
                expense_amount=exp_amt,
                user_messages=user_messages,
            )
        )

        plan_desc = "|".join(f"{p.payment_date.isoformat()}:{p.amount}" for p in plan_payments) or "none"
        return ResilienceReport(
            label="RESILIENCE ANALYSIS",
            plan_description=plan_desc,
            is_baseline_safe=baseline.safe,
            baseline_safety_margin=baseline.safety_margin,
            stress_results=tuple(stress_results),
        )

    def _simulate_salary_delay(
        self,
        state: FinancialState,
        plan_payments: Sequence[ProposedPayment],
        spending_changes: Sequence[SpendingChange],
        delay_days: int,
        base_salary_date: date,
        user_messages: Sequence[Mapping[str, str]],
    ) -> ResilienceScenarioResult:
        """Stress-test delaying the primary payroll event."""
        delayed_date = base_salary_date + timedelta(days=delay_days)
        simulated_messages = list(user_messages) + [
            {
                "message_id": f"sim_delay_{delay_days}d",
                "user_id": state.user_id,
                "request_id": state.request_id,
                "message_date": state.request_date.isoformat(),
                "message_text": f"Payroll will be delayed until {delayed_date.isoformat()}",
                "related_event_id": "",
            }
        ]


        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=plan_payments,
            spending_changes=spending_changes,
            user_messages=simulated_messages,
        )

        return ResilienceScenarioResult(
            stress_test_name=f"SALARY_DELAY_{delay_days}_DAYS",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            description=f"Payroll delayed by {delay_days} days (from {base_salary_date} to {delayed_date})",
        )

    def _simulate_unexpected_expense(
        self,
        state: FinancialState,
        plan_payments: Sequence[ProposedPayment],
        spending_changes: Sequence[SpendingChange],
        expense_amount: Decimal,
        user_messages: Sequence[Mapping[str, str]],
    ) -> ResilienceScenarioResult:
        """Stress-test with an unexpected emergency expense 7 days after request date."""
        shock_date = state.request_date + timedelta(days=7)
        augmented_payments = list(plan_payments) + [
            ProposedPayment(payment_date=shock_date, amount=expense_amount)
        ]

        result = self._forecast_engine.forecast(
            state=state,
            proposed_payment_plan=augmented_payments,
            spending_changes=spending_changes,
            user_messages=user_messages,
        )

        return ResilienceScenarioResult(
            stress_test_name=f"UNEXPECTED_EXPENSE_{expense_amount}",
            is_safe=result.safe,
            lowest_balance=result.lowest_balance,
            lowest_balance_date=result.lowest_balance_date,
            safety_margin=result.safety_margin,
            description=f"Unexpected emergency expense of {expense_amount} on {shock_date}",
        )

    @staticmethod
    def _find_next_salary_date(request_date: date, payroll_events: Sequence[NormalizedEvent]) -> date:
        """Find the next upcoming salary payment date based on historical payroll cadence."""
        if not payroll_events:
            return request_date + timedelta(days=15)

        salary_day = (payroll_events[-1].settlement_date or payroll_events[-1].event_date).day
        try:
            target = date(request_date.year, request_date.month, salary_day)
        except ValueError:
            target = date(request_date.year, request_date.month, 28)

        if target <= request_date:
            m = request_date.month + 1
            y = request_date.year + (m - 1) // 12
            m = (m - 1) % 12 + 1
            try:
                target = date(y, m, salary_day)
            except ValueError:
                target = date(y, m, 28)

        return target
