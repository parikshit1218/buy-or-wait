"""Deterministic generation of grounded decision explanations matching sample conventions."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from candidate_plan_service import CandidatePlan
from financial_state_service import FinancialState
from forecast_engine import SpendingChange
from models import FinancialRequest


_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def _format_date(d: date) -> str:
    """Format date as 'D Month YYYY' (e.g. 15 November 2019)."""
    return f"{d.day} {_MONTH_NAMES[d.month]} {d.year}"


def _format_money(amount: Decimal, currency: str) -> str:
    """Format monetary amount with comma separators, preserving significant cents."""
    if amount == amount.to_integral():
        formatted_num = f"{int(amount):,}"
    else:
        # Check if 2 decimal places
        formatted_num = f"{amount:,.2f}"
    return f"{currency} {formatted_num}"


class DecisionExplanationService:
    """Generates concise, factual, and consistent decision explanations."""

    def generate_explanation(
        self,
        request: FinancialRequest,
        state: FinancialState,
        plan: CandidatePlan,
        amount_safe_to_pay: Decimal,
        earliest_full_payment_date: date | None,
    ) -> str:
        """Produce the natural language decision explanation string."""
        currency = state.home_currency
        min_bal_str = _format_money(state.minimum_balance_to_keep, currency)
        req_amt_str = _format_money(request.requested_amount, currency)

        if plan.method == "full_payment":
            if not plan.spending_changes:
                return (
                    f"Pay {req_amt_str} today. This leaves at least {min_bal_str} "
                    f"available over the next 90 days."
                )
            else:
                changes_text = self._describe_spending_changes(plan.spending_changes, state, currency)
                return (
                    f"{changes_text}, then pay {req_amt_str} today. "
                    f"This leaves at least {min_bal_str} available."
                )

        elif plan.method == "installments":
            count = plan.payment_count
            inst_amt = plan.payments[0].amount if plan.payments else Decimal("0")
            inst_amt_str = _format_money(inst_amt, currency)
            start_date_str = _format_date(plan.first_payment_date or request.request_date)
            return (
                f"Use {count} installments of {inst_amt_str}, starting {start_date_str}. "
                f"This leaves at least {min_bal_str} available."
            )

        elif plan.method == "partial_payment":
            safe_now_str = _format_money(amount_safe_to_pay, currency)
            rem_amt = request.requested_amount - amount_safe_to_pay
            rem_amt_str = _format_money(rem_amt, currency)
            second_date_str = _format_date(earliest_full_payment_date or request.request_date)
            return (
                f"Pay {safe_now_str} today and the remaining {rem_amt_str} on {second_date_str}. "
                f"This completes the full request and keeps the {min_bal_str} minimum protected."
            )

        elif plan.method == "wait":
            wait_date_str = _format_date(earliest_full_payment_date or request.desired_completion_date)
            return (
                f"Pay {req_amt_str} in full on {wait_date_str}. "
                f"Paying earlier would take the balance below the {min_bal_str} minimum."
            )

        else:  # not_recommended / not_affordable
            if earliest_full_payment_date is None and amount_safe_to_pay > Decimal("0"):
                safe_now_str = _format_money(amount_safe_to_pay, currency)
                return (
                    f"Do not proceed with the {req_amt_str} request. "
                    f"Although {safe_now_str} is available today, the full amount "
                    f"cannot be completed safely within 90 days."
                )
            else:
                deadline_str = _format_date(request.desired_completion_date)
                return (
                    f"Do not make this payment by {deadline_str}. "
                    f"None of the available options keeps the {min_bal_str} minimum protected."
                )

    def _describe_spending_changes(
        self,
        changes: Sequence[SpendingChange],
        state: FinancialState,
        currency: str,
    ) -> str:
        descriptions: list[str] = []
        events_by_id = {e.event_id: e for e in state.events}

        for sc in changes:
            event = events_by_id.get(sc.event_id)
            desc_name = event.description.lower() if event else sc.event_id
            if sc.action_type == "stop":
                descriptions.append(f"stop the {desc_name}")
            elif sc.action_type == "reduce_to":
                target_str = _format_money(sc.target_amount, currency)
                descriptions.append(f"reduce the {desc_name} to {target_str}")

        if not descriptions:
            return "Adjust spending"

        if len(descriptions) == 1:
            return descriptions[0].capitalize()
        elif len(descriptions) == 2:
            return f"{descriptions[0].capitalize()} and {descriptions[1]}"
        else:
            return f"{descriptions[0].capitalize()}, {descriptions[1]}, and {descriptions[2]}"

