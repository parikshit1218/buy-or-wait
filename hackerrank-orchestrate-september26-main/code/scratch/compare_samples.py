"""Compare agent predictions against sample_requests.csv ground truth."""

import csv
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import DataLoader
from decision_agent import DecisionAgent
from models import FinancialRequest

def main():
    agent = DecisionAgent("dataset")
    samples = agent.loader.load_sample_requests()

    mismatches = []
    total = len(samples)

    for s in samples:
        req = FinancialRequest(
            request_id=s.request_id,
            user_id=s.user_id,
            request_date=s.request_date,
            request_type=s.request_type,
            requested_amount=s.requested_amount,
            desired_completion_date=s.desired_completion_date,
            allows_partial_payment=s.allows_partial_payment,
            request_text=s.request_text,
        )
        pred = agent.evaluate_request(req)

        fields = [
            ("amount_safe_to_pay", s.amount_safe_to_pay, pred.amount_safe_to_pay),
            ("affordability_status", s.affordability_status, pred.affordability_status),
            ("recommended_payment_method", s.recommended_payment_method, pred.recommended_payment_method),
            ("payment_plan", s.payment_plan, pred.payment_plan),
            ("earliest_date_for_full_payment", s.earliest_date_for_full_payment, pred.earliest_date_for_full_payment),
            ("spending_changes_needed", s.spending_changes_needed, pred.spending_changes_needed),
        ]

        diffs = {}
        for fld, expected, actual in fields:
            if isinstance(expected, Decimal) or isinstance(actual, Decimal):
                exp_dec = Decimal(str(expected)) if expected is not None else None
                act_dec = Decimal(str(actual)) if actual is not None else None
                if exp_dec != act_dec:
                    diffs[fld] = {"expected": str(expected), "actual": str(actual)}
            elif expected != actual:
                # Format dates / strings
                exp_str = expected.isoformat() if hasattr(expected, "isoformat") else ("" if expected is None else str(expected).strip())
                act_str = actual.isoformat() if hasattr(actual, "isoformat") else ("" if actual is None else str(actual).strip())
                if exp_str != act_str:
                    diffs[fld] = {"expected": exp_str, "actual": act_str}

        if diffs:
            mismatches.append({"request_id": s.request_id, "diffs": diffs})

    print(f"Total samples: {total}, Exact Matches: {total - len(mismatches)}, Mismatches: {len(mismatches)}")
    for m in mismatches:
        print(f"\n--- {m['request_id']} ---")
        for fld, d in m["diffs"].items():
            print(f"  {fld}:\n    expected: {d['expected']}\n    actual:   {d['actual']}")

if __name__ == "__main__":
    main()

