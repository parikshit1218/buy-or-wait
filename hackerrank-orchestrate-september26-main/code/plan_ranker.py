"""Multi-criteria ranking and selection for candidate payment plans."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Sequence

from candidate_plan_service import CandidatePlan


class PlanRanker:
    """Ranks eligible candidate plans using the exact 6-tier preference hierarchy.

    Hierarchy:
    1. Completes full request by desired_completion_date (True before False)
    2. Requires fewer / no spending changes (0 changes best)
    3. Minimizes total amount paid (total_payable_amount)
    4. Starts earlier (earlier first_payment_date)
    5. Uses fewer payments (fewer installments/splits)
    6. Lowest payment_option_id (tie-breaker)
    """

    def select_best_plan(
        self,
        candidates: Sequence[CandidatePlan],
        desired_completion_date: date,
    ) -> CandidatePlan:
        """Select the highest-ranked safe plan among the candidates."""
        safe_candidates = [c for c in candidates if c.is_safe and c.method != "not_recommended"]
        if not safe_candidates:
            # Return not_recommended fallback
            for c in candidates:
                if c.method == "not_recommended":
                    return c
            raise ValueError("No candidates provided including fallback")

        # Filter candidates that complete by desired deadline first if any exist
        return min(safe_candidates, key=lambda plan: self._ranking_key(plan, desired_completion_date))

    def _ranking_key(
        self,
        plan: CandidatePlan,
        deadline: date,
    ) -> tuple[int, int, Decimal, date, int, str]:
        # 1. Complete by deadline (0 = Yes, 1 = No)
        completes_by_deadline_score = 0 if plan.completes_by_deadline else 1

        # 2. Number of spending changes (0, 1, 2, 3)
        spending_changes_count = len(plan.spending_changes)

        # 3. Total amount paid
        total_amount = plan.total_payable_amount

        # 4. First payment date (earlier is better)
        first_date = plan.first_payment_date or date.max

        # 5. Fewer payments
        payments_count = plan.payment_count

        # 6. Lowest payment option ID (tie-breaker)
        option_id = plan.payment_option_id or "zzzzzz"

        return (
            completes_by_deadline_score,
            spending_changes_count,
            total_amount,
            first_date,
            payments_count,
            option_id,
        )

