"""Deterministic 90-day balance forecasting for reconstructed financial state."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Iterable, Mapping, Sequence

from financial_state_service import FinancialState, NormalizedEvent
from message_interpreter import MessageFact, MessageInterpreter


ZERO = Decimal("0")


@dataclass(frozen=True)
class ProposedPayment:
    """A proposed payment date and monetary amount."""

    payment_date: date
    amount: Decimal


@dataclass(frozen=True)
class SpendingChange:
    """A flexible expense modification (stop or reduce)."""

    action_type: str  # "stop" or "reduce_to"
    event_id: str
    target_amount: Decimal = ZERO  # Used when action_type == "reduce_to"

    def to_str(self) -> str:
        if self.action_type == "stop":
            return f"stop:{self.event_id}"
        return f"reduce_to:{self.event_id}:{self.target_amount}"


@dataclass(frozen=True)
class ForecastResult:
    """Outcome of 90-day forward cash flow simulation."""

    daily_balances: Mapping[date, Decimal]
    lowest_balance: Decimal
    lowest_balance_date: date
    safety_margin: Decimal
    safe: bool


class ForecastEngine:
    """Forecast end-of-day balances from request date through day 90 inclusive.

    The engine uses only the reconstructed facts supplied in ``FinancialState``
    and any confirmed salary adjustments from user messages.
    """

    FORECAST_DAYS = 90
    _RECURRENCE_TOLERANCE_DAYS = 7

    def __init__(self, message_interpreter: MessageInterpreter | None = None) -> None:
        self._message_interpreter = message_interpreter or MessageInterpreter()

    def forecast(
        self,
        state: FinancialState,
        proposed_payment_plan: Iterable[ProposedPayment] = (),
        spending_changes: Iterable[SpendingChange] = (),
        user_messages: Sequence[Mapping[str, str]] = (),
    ) -> ForecastResult:
        """Run a 90-day daily balance projection from state.request_date."""
        end_date = state.request_date + timedelta(days=self.FORECAST_DAYS)
        changes: dict[date, Decimal] = defaultdict(lambda: ZERO)

        # Parse spending changes
        stop_event_ids: set[str] = set()
        reduce_event_amounts: dict[str, Decimal] = {}
        for sc in spending_changes:
            if sc.action_type == "stop":
                stop_event_ids.add(sc.event_id)
            elif sc.action_type == "reduce_to":
                reduce_event_amounts[sc.event_id] = sc.target_amount

        # 1. Apply confirmed events in state.events
        known_future_cash_dates: set[date] = set()
        for event in state.events:
            self._apply_event(
                event,
                state.request_date,
                end_date,
                changes,
                stop_event_ids,
                reduce_event_amounts,
                known_future_cash_dates,
            )

        # 2. Project recurring debits based on past cadence
        self._apply_recurring_debit_projections(
            state,
            end_date,
            changes,
            stop_event_ids,
            reduce_event_amounts,
        )

        # 3. Project recurring salary / confirmed income
        self._apply_recurring_income_projections(
            state,
            end_date,
            changes,
            user_messages,
        )

        # 4. Apply proposed payment plan
        for payment in proposed_payment_plan:
            self._apply_payment(payment, state.request_date, end_date, changes)

        # 5. Build daily trajectory
        daily_balances: dict[date, Decimal] = {}
        balance = state.available_balance
        current_day = state.request_date
        lowest_balance: Decimal | None = None
        lowest_balance_date: date | None = None

        while current_day <= end_date:
            balance += changes[current_day]
            daily_balances[current_day] = balance
            if lowest_balance is None or balance < lowest_balance:
                lowest_balance = balance
                lowest_balance_date = current_day
            current_day += timedelta(days=1)

        assert lowest_balance is not None and lowest_balance_date is not None
        margin = lowest_balance - state.minimum_balance_to_keep
        return ForecastResult(
            daily_balances=daily_balances,
            lowest_balance=lowest_balance,
            lowest_balance_date=lowest_balance_date,
            safety_margin=margin,
            safe=margin >= ZERO,
        )

    @staticmethod
    def _apply_payment(
        payment: ProposedPayment,
        start_date: date,
        end_date: date,
        changes: dict[date, Decimal],
    ) -> None:
        if not isinstance(payment.amount, Decimal):
            raise TypeError("Proposed payment amounts must be Decimal")
        if payment.amount < ZERO:
            raise ValueError("Proposed payment amounts cannot be negative")
        if start_date <= payment.payment_date <= end_date:
            changes[payment.payment_date] -= payment.amount

    @staticmethod
    def _apply_event(
        event: NormalizedEvent,
        start_date: date,
        end_date: date,
        changes: dict[date, Decimal],
        stop_event_ids: set[str],
        reduce_event_amounts: dict[str, Decimal],
        known_future_dates: set[date],
    ) -> None:
        if not event.included_in_cash_state or event.amount_home_currency is None:
            return
        effective_date = event.settlement_date or event.event_date
        if effective_date < start_date or effective_date > end_date:
            return

        known_future_dates.add(effective_date)
        amt = event.amount_home_currency
        if event.event_id in stop_event_ids:
            return
        elif event.event_id in reduce_event_amounts:
            amt = reduce_event_amounts[event.event_id]

        if event.direction == "debit":
            changes[effective_date] -= amt
        elif event.direction == "credit" and ForecastEngine._is_confirmed_credit(event):
            changes[effective_date] += amt

    @staticmethod
    def _is_confirmed_credit(event: NormalizedEvent) -> bool:
        if event.is_confirmed_income:
            return True
        return event.status == "settled" and event.financial_meaning in {"refund", "investment", "other"}

    def _apply_recurring_debit_projections(
        self,
        state: FinancialState,
        end_date: date,
        changes: dict[date, Decimal],
        stop_event_ids: set[str],
        reduce_event_amounts: dict[str, Decimal],
    ) -> None:
        # Group historical debits before request_date
        past_debits = [
            e for e in state.events
            if e.included_in_cash_state and e.direction == "debit" and (e.settlement_date or e.event_date) < state.request_date
        ]

        # Specific bills grouped by (category, description) if specific fixed bills, else by category
        group_map: dict[tuple[str, str], list[NormalizedEvent]] = defaultdict(list)
        for e in past_debits:
            key = (e.category, e.description) if e.category in (
                "subscription", "rent", "debt_repayment", "education", "utilities", "family_support", "insurance", "cloud_storage", "healthcare"
            ) else (e.category, "")
            group_map[key].append(e)

        cur_year = state.request_date.year
        cur_month = state.request_date.month

        for (cat, desc), evts in group_map.items():
            ordered = sorted(evts, key=lambda x: x.settlement_date or x.event_date)
            if len(ordered) < 2:
                continue
            dates = [x.settlement_date or x.event_date for x in ordered]
            intervals = [(r - l).days for l, r in zip(dates, dates[1:]) if (r - l).days > 0]
            if not intervals:
                continue
            interval = int(median(intervals))
            if interval <= 0:
                continue

            last_evt = ordered[-1]
            last_date = dates[-1]
            base_amt = last_evt.amount_home_currency
            if base_amt is None:
                continue

            stream_event_ids = {x.event_id for x in ordered}
            if any(eid in stop_event_ids for eid in stream_event_ids):
                continue
            for eid in stream_event_ids:
                if eid in reduce_event_amounts:
                    base_amt = reduce_event_amounts[eid]

            # If monthly stream (interval ~28-31 days or recognized monthly category)
            if 28 <= interval <= 31 or cat in ("subscription", "rent", "debt_repayment", "education", "utilities", "family_support", "insurance", "cloud_storage", "healthcare"):
                bill_day = last_date.day
                for m_offset in range(4):
                    m = cur_month + m_offset
                    y = cur_year + (m - 1) // 12
                    m = (m - 1) % 12 + 1
                    try:
                        bill_d = date(y, m, bill_day)
                    except ValueError:
                        bill_d = date(y, m, 28)
                    if state.request_date <= bill_d <= end_date:
                        changes[bill_d] -= base_amt
            else:
                next_d = last_date + timedelta(days=interval)
                while next_d <= end_date:
                    if next_d >= state.request_date:
                        changes[next_d] -= base_amt
                    next_d += timedelta(days=interval)


    def _apply_recurring_income_projections(
        self,
        state: FinancialState,
        end_date: date,
        changes: dict[date, Decimal],
        user_messages: Sequence[Mapping[str, str]],
    ) -> None:
        inc_events = [
            e for e in state.events
            if e.event_type.lower() == "income"
            and e.included_in_cash_state
            and (e.settlement_date or e.event_date) < state.request_date
        ]
        payroll_events = [
            e for e in inc_events
            if "payroll" in e.description.lower() or "salary" in e.description.lower() or "contract" in e.description.lower() or "wages" in e.description.lower()
        ]
        is_final_payroll = any("final employer payroll" in e.description.lower() for e in payroll_events)
        if not payroll_events or is_final_payroll:
            return

        # Inspect messages for salary updates
        user_fact: MessageFact | None = None
        for m in user_messages:
            facts = self._message_interpreter.interpret(m)
            for f in facts:
                if f.amendment_type in ("salary_change", "salary_delay"):
                    user_fact = f

        actual_inc_dates = {
            e.settlement_date or e.event_date
            for e in inc_events
            if state.request_date <= (e.settlement_date or e.event_date) <= end_date
            and (e.is_confirmed_income or e.status == "scheduled")
        }

        # Group by distinct recurring payroll stream: (description, day of month)
        stream_groups: dict[tuple[str, int], list[NormalizedEvent]] = defaultdict(list)
        for e in payroll_events:
            d = e.settlement_date or e.event_date
            stream_groups[(e.description, d.day)].append(e)

        cur_year = state.request_date.year
        cur_month = state.request_date.month

        for (desc, salary_day), evts in stream_groups.items():
            ordered = sorted(evts, key=lambda e: e.settlement_date or e.event_date)
            last_inc = ordered[-1]
            salary_amt = last_inc.amount_home_currency
            if salary_amt is None or salary_amt <= ZERO:
                continue

            delayed_date: date | None = None
            if user_fact:
                if user_fact.amendment_type == "salary_change":
                    if user_fact.amount is not None:
                        salary_amt = user_fact.amount
                elif user_fact.amendment_type == "salary_delay":
                    if user_fact.date is not None:
                        delayed_date = user_fact.date
                    if user_fact.amount is not None:
                        salary_amt = user_fact.amount

            for m_offset in range(4):
                m = cur_month + m_offset
                y = cur_year + (m - 1) // 12
                m = (m - 1) % 12 + 1
                try:
                    pay_d = date(y, m, salary_day)
                except ValueError:
                    pay_d = date(y, m, 28)

                if m_offset == 0 and delayed_date and delayed_date >= state.request_date:
                    pay_d = delayed_date

                if state.request_date <= pay_d <= end_date:
                    if pay_d not in actual_inc_dates and not any(
                        abs((a - pay_d).days) <= self._RECURRENCE_TOLERANCE_DAYS for a in actual_inc_dates
                    ):
                        changes[pay_d] += salary_amt

