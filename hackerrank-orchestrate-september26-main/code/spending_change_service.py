"""Spending change identification and candidate combination generation."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import SpendingChange
from models import FinancialProfile


@dataclass(frozen=True)
class FlexibleOption:
    """An identified flexible action on a specific event."""

    event: NormalizedEvent
    action_type: str  # "stop" or "reduce_to"
    target_amount: Decimal

    def to_spending_change(self) -> SpendingChange:
        return SpendingChange(
            action_type=self.action_type,
            event_id=self.event.event_id,
            target_amount=self.target_amount,
        )


class SpendingChangeService:
    """Discovers allowed spending adjustments from user profile and financial state."""

    MAX_CHANGES = 3

    def get_flexible_options(
        self,
        profile: FinancialProfile,
        state: FinancialState,
    ) -> list[FlexibleOption]:
        """Find all individual valid spending changes the user permits."""
        protected = set(profile.expense_categories_to_protect)
        can_stop_cats = set(profile.expense_categories_user_is_willing_to_stop)
        can_reduce_cats = set(profile.expense_categories_user_is_willing_to_reduce)

        options: list[FlexibleOption] = []
        seen_events: set[str] = set()

        # Find candidate debits in historical/recurring ledger
        candidate_events = [
            e for e in state.events
            if e.included_in_cash_state
            and e.direction == "debit"
            and e.category not in protected
            and e.amount_home_currency is not None
            and e.amount_home_currency > Decimal("0")
        ]

        # Sort by most recent first
        candidate_events.sort(
            key=lambda x: x.settlement_date or x.event_date,
            reverse=True,
        )

        for event in candidate_events:
            # We only need the latest occurrence per stream
            stream_key = (event.category, event.description)
            if stream_key in seen_events:
                continue
            seen_events.add(stream_key)

            is_stoppable = (
                event.flexibility == "stoppable"
                or event.category in can_stop_cats
            )
            if is_stoppable:
                options.append(
                    FlexibleOption(
                        event=event,
                        action_type="stop",
                        target_amount=Decimal("0"),
                    )
                )

            is_reducible = (
                event.flexibility == "reducible"
                or event.category in can_reduce_cats
            )
            if is_reducible and event.minimum_allowed_amount is not None:
                if event.minimum_allowed_amount < (event.amount_home_currency or Decimal("0")):
                    options.append(
                        FlexibleOption(
                            event=event,
                            action_type="reduce_to",
                            target_amount=event.minimum_allowed_amount,
                        )
                    )

        return options

    def generate_change_combinations(
        self,
        options: Sequence[FlexibleOption],
    ) -> list[tuple[SpendingChange, ...]]:
        """Generate valid combinations of 0 to MAX_CHANGES spending changes.

        Ensures that no event is both stopped and reduced in the same combination.
        """
        combinations: list[tuple[SpendingChange, ...]] = [()]

        for r in range(1, min(self.MAX_CHANGES + 1, len(options) + 1)):
            for comb in itertools.combinations(options, r):
                # Verify distinct events
                event_ids = [opt.event.event_id for opt in comb]
                if len(set(event_ids)) == len(event_ids):
                    spending_changes = tuple(opt.to_spending_change() for opt in comb)
                    combinations.append(spending_changes)

        return combinations

