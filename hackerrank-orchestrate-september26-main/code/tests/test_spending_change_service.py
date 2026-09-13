"""Unit tests for Phase 7: SpendingChangeService and spending change optimizer.

Requirements:
- Only recurring expenses marked flexible may be modified.
- Supported outputs:
    stop:<event_id>
    reduce_to:<event_id>:<new_amount>
- Maximum 3 changes
- Never modify non-flexible events
- Stop and reduce cannot target same event
- Never invent an event
- Changes must actually improve feasibility
- Search for the smallest useful set of changes
- Do not modify official candidate ranking rules
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from candidate_plan_service import CandidatePlanService
from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment, SpendingChange
from models import FinancialProfile, FinancialRequest
from plan_ranker import PlanRanker
from spending_change_service import FlexibleOption, SpendingChangeService


class SpendingChangeServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = SpendingChangeService()
        self.forecast_engine = ForecastEngine()
        self.candidate_service = CandidatePlanService(self.forecast_engine, self.service)
        self.ranker = PlanRanker()
        self.request_date = date(2026, 5, 1)

    def make_profile(
        self,
        *,
        protect: tuple[str, ...] = (),
        reduce_cats: tuple[str, ...] = (),
        stop_cats: tuple[str, ...] = (),
        balance: str = "1000",
        minimum: str = "200",
    ) -> FinancialProfile:
        return FinancialProfile(
            user_id="user_test",
            home_currency="USD",
            current_available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            financial_priorities=("savings",),
            expense_categories_to_protect=protect,
            expense_categories_user_is_willing_to_reduce=reduce_cats,
            expense_categories_user_is_willing_to_stop=stop_cats,
            payment_methods_user_will_consider=("full_payment", "installments"),
            max_installment_months=6,
        )

    def make_event(
        self,
        event_id: str,
        category: str,
        *,
        direction: str = "debit",
        amount: str = "100",
        flexibility: str = "fixed",
        minimum_allowed_amount: str | None = None,
        is_recurring: bool = True,
        day: date | None = None,
    ) -> NormalizedEvent:
        amt = Decimal(amount)
        min_amt = Decimal(minimum_allowed_amount) if minimum_allowed_amount is not None else None
        event_day = day or date(2026, 4, 15)
        return NormalizedEvent(
            event_id=event_id,
            user_id="user_test",
            event_type="expense" if direction == "debit" else "income",
            description=f"Description for {event_id}",
            category=category,
            direction=direction,
            amount=amt,
            currency="USD",
            amount_home_currency=amt,
            conversion_rate=Decimal("1"),
            conversion_rate_date=event_day,
            amount_source="financial_events.csv",
            event_date=event_day,
            settlement_date=event_day,
            status="settled",
            linked_event_id=None,
            flexibility=flexibility,
            minimum_allowed_amount=min_amt,
            financial_meaning="expense" if direction == "debit" else "income",
            is_recurring=is_recurring,
            is_confirmed_income=direction == "credit",
            is_confirmed_future_payment=False,
            is_refund=False,
            is_transfer=False,
            included_in_cash_state=True,
            exclusion_reason=None,
            evidence_resolution=None,
        )

    def make_state(self, events: tuple[NormalizedEvent, ...], balance: str = "1000", minimum: str = "200") -> FinancialState:
        return FinancialState(
            request_id="req_test",
            user_id="user_test",
            request_date=self.request_date,
            home_currency="USD",
            available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            events=events,
            recurring_expenses=tuple(e for e in events if e.is_recurring),
            one_time_expenses=tuple(e for e in events if not e.is_recurring),
            confirmed_income=(),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    def test_maximum_3_changes_enforced(self):
        """Rule: maximum 3 changes per candidate plan."""
        # 5 distinct flexible events
        events = tuple(
            self.make_event(f"e{i}", f"cat_{i}", flexibility="stoppable")
            for i in range(1, 6)
        )
        profile = self.make_profile()
        state = self.make_state(events)

        options = self.service.get_flexible_options(profile, state)
        self.assertEqual(len(options), 5)

        combinations = self.service.generate_change_combinations(options)
        for comb in combinations:
            self.assertLessEqual(len(comb), 3, "No combination should exceed 3 spending changes")

    def test_never_modify_protected_events(self):
        """Rule: never modify non-flexible / protected events."""
        ev1 = self.make_event("e1", "rent", flexibility="stoppable")
        ev2 = self.make_event("e2", "groceries", flexibility="reducible", minimum_allowed_amount="50")
        ev3 = self.make_event("e3", "streaming", flexibility="stoppable")

        # Protect rent and groceries
        profile = self.make_profile(protect=("rent", "groceries"))
        state = self.make_state((ev1, ev2, ev3))

        options = self.service.get_flexible_options(profile, state)
        option_ids = {opt.event.event_id for opt in options}

        self.assertNotIn("e1", option_ids, "Protected rent must not be modified")
        self.assertNotIn("e2", option_ids, "Protected groceries must not be modified")
        self.assertIn("e3", option_ids, "Unprotected streaming can be stopped")

    def test_never_modify_fixed_events_without_profile_permission(self):
        """Rule: fixed events with no user category permission must not be modified."""
        ev_fixed = self.make_event("e_fixed", "utilities", flexibility="fixed")
        profile = self.make_profile(stop_cats=("streaming",), reduce_cats=("dining",))
        state = self.make_state((ev_fixed,))

        options = self.service.get_flexible_options(profile, state)
        self.assertEqual(len(options), 0, "Fixed event without permission must not be modified")

    def test_profile_category_permissions_enable_flexibility(self):
        """Category permissions in profile allow stopping/reducing matching events."""
        ev1 = self.make_event("e1", "streaming", flexibility="fixed")
        ev2 = self.make_event("e2", "dining", flexibility="fixed", amount="100", minimum_allowed_amount="40")

        profile = self.make_profile(stop_cats=("streaming",), reduce_cats=("dining",))
        state = self.make_state((ev1, ev2))

        options = self.service.get_flexible_options(profile, state)
        action_map = {opt.event.event_id: opt.action_type for opt in options}

        self.assertEqual(action_map.get("e1"), "stop")
        self.assertEqual(action_map.get("e2"), "reduce_to")

    def test_stop_and_reduce_cannot_target_same_event_in_single_combination(self):
        """Rule: stop and reduce cannot target the same event."""
        # Event that could be both stopped and reduced
        ev = self.make_event("e_multi", "dining", flexibility="stoppable", amount="100", minimum_allowed_amount="30")
        profile = self.make_profile(stop_cats=("dining",), reduce_cats=("dining",))
        state = self.make_state((ev,))

        options = self.service.get_flexible_options(profile, state)
        # Options list can have both stop and reduce_to as individual possibilities
        self.assertGreaterEqual(len(options), 2)

        combinations = self.service.generate_change_combinations(options)
        for comb in combinations:
            event_ids = [sc.event_id for sc in comb]
            self.assertEqual(
                len(event_ids),
                len(set(event_ids)),
                "A single combination must never contain duplicate event_ids",
            )

    def test_never_invent_an_event(self):
        """Rule: all spending change event IDs must exist in state.events."""
        ev1 = self.make_event("real_event_1", "streaming", flexibility="stoppable")
        ev2 = self.make_event("real_event_2", "dining", flexibility="reducible", minimum_allowed_amount="25")
        profile = self.make_profile()
        state = self.make_state((ev1, ev2))

        options = self.service.get_flexible_options(profile, state)
        combinations = self.service.generate_change_combinations(options)

        valid_ids = {"real_event_1", "real_event_2"}
        for comb in combinations:
            for sc in comb:
                self.assertIn(sc.event_id, valid_ids, f"Event {sc.event_id} was not in supplied state events")

    def test_reduce_to_requires_valid_lower_amount(self):
        """reduce_to is only valid if minimum_allowed_amount is less than current amount."""
        ev_invalid = self.make_event(
            "e_invalid", "dining", flexibility="reducible", amount="50", minimum_allowed_amount="50"
        )
        ev_none = self.make_event(
            "e_none", "dining", flexibility="reducible", amount="50", minimum_allowed_amount=None
        )
        profile = self.make_profile()
        state = self.make_state((ev_invalid, ev_none))

        options = self.service.get_flexible_options(profile, state)
        self.assertEqual(len(options), 0, "No reduce_to should be generated when amount cannot be decreased")

    def test_supported_output_string_formats(self):
        """Supported outputs: stop:<event_id> and reduce_to:<event_id>:<new_amount>."""
        sc_stop = SpendingChange("stop", "event_101")
        sc_reduce = SpendingChange("reduce_to", "event_202", Decimal("45.50"))

        self.assertEqual(sc_stop.to_str(), "stop:event_101")
        self.assertEqual(sc_reduce.to_str(), "reduce_to:event_202:45.50")

        # Formatted pipe combination
        formatted = CandidatePlanService._format_spending_changes((sc_stop, sc_reduce))
        self.assertEqual(formatted, "stop:event_101|reduce_to:event_202:45.50")

        # Empty combination
        empty_formatted = CandidatePlanService._format_spending_changes(())
        self.assertEqual(empty_formatted, "none")

    def test_smallest_useful_set_of_changes_ranked_highest(self):
        """Search selects the smallest set of changes (1 change > 2 changes > 3 changes)."""
        req = FinancialRequest(
            request_id="req_rank",
            user_id="user_test",
            request_date=self.request_date,
            request_type="purchase",
            requested_amount=Decimal("300"),
            desired_completion_date=self.request_date + timedelta(days=30),
            allows_partial_payment=False,
            request_text="Buy item",
        )
        profile = self.make_profile(balance="600", minimum="200")
        # 600 - 300 = 300.
        # With sub (60) and gym (70): 300 - 60 - 70 = 170 < 200 (unsafe with 0 changes!)
        # With 1 change (stop gym): 300 - 60 = 240 >= 200 (safe with 1 change!)
        # With 2 changes (stop gym + stop sub): 300 >= 200 (safe with 2 changes!)
        ev_sub = self.make_event("sub_1", "subscription", flexibility="stoppable", amount="60", day=self.request_date - timedelta(days=30))
        ev_gym = self.make_event("gym_1", "fitness", flexibility="stoppable", amount="70", day=self.request_date - timedelta(days=30))
        # 2 events repeated monthly
        ev_sub_prev = self.make_event("sub_0", "subscription", flexibility="stoppable", amount="60", day=self.request_date - timedelta(days=60))
        ev_gym_prev = self.make_event("gym_0", "fitness", flexibility="stoppable", amount="70", day=self.request_date - timedelta(days=60))

        state = self.make_state((ev_sub_prev, ev_sub, ev_gym_prev, ev_gym), balance="600", minimum="200")

        candidates = self.candidate_service.generate_candidate_plans(
            request=req,
            profile=profile,
            state=state,
            payment_options=(),
            amount_safe_to_pay=Decimal("170"),
            earliest_full_payment_date=None,  # No wait plan possible
        )

        best_plan = self.ranker.select_best_plan(candidates, req.desired_completion_date)
        # 1 change is sufficient to reach safety, so 1 change must be picked instead of 2 changes
        self.assertEqual(len(best_plan.spending_changes), 1)
        self.assertTrue(best_plan.is_safe)
        self.assertEqual(best_plan.affordability_status, "affordable_with_plan")


if __name__ == "__main__":
    unittest.main()
