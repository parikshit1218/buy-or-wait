"""Main entry point for Buy or Wait? financial decision agent."""

from __future__ import annotations

import argparse
from decimal import Decimal
import sys
from pathlib import Path


from config import DEFAULT_DATASET_DIR, REPO_ROOT
from data_loader import DataLoader
from validators import validate_dataset


def run_check_data(dataset_dir: Path) -> int:
    """Audit datasets and print comprehensive integrity report."""
    print("=" * 70)
    print(" BUY OR WAIT? -- DATASET INTEGRITY & VALIDATION REPORT")
    print("=" * 70)
    print(f"Dataset path: {dataset_dir.resolve()}\n")

    try:
        loader = DataLoader(dataset_dir)
        ctx = loader.load_all()
    except Exception as exc:
        print(f"FAILED TO LOAD DATASET: {exc}", file=sys.stderr)
        return 1

    media_dir = dataset_dir / "media" / "images"
    report = validate_dataset(ctx, media_dir=media_dir if media_dir.is_dir() else None)

    print(f"* Number of evaluation requests:   {report.total_requests}")
    print(f"* Number of sample requests:       {report.total_samples}")
    print(f"* Total requests (eval + sample):  {report.total_requests + report.total_samples}")
    print(f"* Number of profiles:              {report.total_profiles}")
    print(f"* Number of financial events:      {report.total_events}")
    print(f"* Number of payment options:       {report.total_options}")
    print(f"* Number of messages:              {report.total_messages}")
    print(f"* Number of images:                {report.total_images}")
    print(f"* Blank financial-event amounts:   {report.blank_event_amounts}")
    if report.blank_event_ids:
        print(f"  Mapped event IDs: {', '.join(report.blank_event_ids)}")

    currencies_sorted = sorted(report.currencies)
    print(f"* Currencies:                      {', '.join(currencies_sorted)}")

    total_missing_joins = sum(report.missing_joins.values())
    print(f"\n* Missing joins:                   {total_missing_joins}")
    for join_name, count in report.missing_joins.items():
        status = "OK" if count == 0 else f"MISSING ({count})"
        print(f"  - {join_name:<30} {status}")

    print("\n" + "-" * 70)
    if report.is_valid:
        print("STATUS: ALL DATA INTEGRITY CHECKS PASSED (0 ERRORS, 0 MISSING JOINS)")
        print("-" * 70)
        return 0
    else:
        print(f"STATUS: VALIDATION FAILED WITH {len(report.errors)} ERRORS")
        for err in report.errors:
            print(f"  [ERROR] {err}")
        print("-" * 70)
        return 1


def run_time_machine(dataset_dir: Path, request_id: str) -> int:
    """Run interactive scenario simulation for a specific request."""
    print("=" * 70)
    print(f" BUY OR WAIT? -- FINANCIAL TIME MACHINE (SCENARIO SIMULATOR)")
    print("=" * 70)
    print(f"Request ID: {request_id}\n")

    loader = DataLoader(dataset_dir)
    ctx = loader.load_all()

    req = ctx.requests_by_id.get(request_id) or ctx.sample_requests_by_id.get(request_id)
    if req is None:
        print(f"Error: request_id '{request_id}' not found in dataset.", file=sys.stderr)
        return 1

    profile = ctx.profiles_by_user.get(req.user_id)
    if profile is None:
        print(f"Error: user profile for '{req.user_id}' not found.", file=sys.stderr)
        return 1

    from financial_state_service import FinancialStateService
    from time_machine import FinancialTimeMachine

    state_service = FinancialStateService(dataset_dir)
    state = state_service.reconstruct(request_id)
    time_machine = FinancialTimeMachine()

    messages = [m.__dict__ for m in ctx.messages_by_user.get(req.user_id, [])]
    options = ctx.options_by_request.get(request_id, [])


    scenarios = time_machine.simulate_all_scenarios(
        request=req,
        profile=profile,
        state=state,
        payment_options=options,
        user_messages=messages,
    )

    print(f"User: {req.user_id} | Currency: {profile.home_currency} | Balance: {state.available_balance} | Min Keep: {state.minimum_balance_to_keep}")
    print(f"Requested Amount: {req.requested_amount} on {req.request_date} (Deadline: {req.desired_completion_date})\n")
    print(f"{'SCENARIO':<25} {'SAFE?':<8} {'LOWEST BAL':<14} {'LOWEST DATE':<14} {'MARGIN':<12} {'COMPLETION':<14} {'TOTAL PAID':<14} {'PAYMENTS'}")
    print("-" * 115)

    for s in scenarios:
        safe_str = "YES" if s.is_safe else "NO"
        comp_str = s.completion_date.isoformat() if s.completion_date else "-"
        low_date_str = s.lowest_balance_date.isoformat() if s.lowest_balance_date else "-"
        print(
            f"{s.scenario_name:<25} {safe_str:<8} {str(s.lowest_balance):<14} {low_date_str:<14} "
            f"{str(s.safety_margin):<12} {comp_str:<14} {str(s.total_amount_paid):<14} {s.number_of_payments}"
        )

    print("-" * 115)
    return 0


def run_resilience_analysis(
    dataset_dir: Path,
    request_id: str,
    unexpected_expense: Decimal | None = None,
) -> int:
    """Run cash flow stress testing and resilience analysis for a specific request's approved plan."""
    print("=" * 70)
    print(" RESILIENCE ANALYSIS (CASH FLOW STRESS TESTING)")
    print("=" * 70)
    print(f"Request ID: {request_id}\n")

    loader = DataLoader(dataset_dir)
    ctx = loader.load_all()

    req = ctx.requests_by_id.get(request_id) or ctx.sample_requests_by_id.get(request_id)
    if req is None:
        print(f"Error: request_id '{request_id}' not found in dataset.", file=sys.stderr)
        return 1

    profile = ctx.profiles_by_user.get(req.user_id)
    if profile is None:
        print(f"Error: user profile for '{req.user_id}' not found.", file=sys.stderr)
        return 1

    from decision_agent import DecisionAgent
    from financial_state_service import FinancialStateService
    from resilience_analysis import ResilienceAnalyzer

    agent = DecisionAgent(dataset_dir)
    out_row = agent.evaluate_request(req)

    state_service = FinancialStateService(dataset_dir)
    state = state_service.reconstruct(request_id)
    analyzer = ResilienceAnalyzer()

    # Parse payments from the chosen plan
    from forecast_engine import ProposedPayment
    from datetime import datetime

    plan_payments: list[ProposedPayment] = []
    if out_row.payment_plan != "none":
        for part in out_row.payment_plan.split("|"):
            if ":" in part:
                d_str, amt_str = part.split(":", 1)
                plan_payments.append(
                    ProposedPayment(
                        payment_date=datetime.strptime(d_str.strip(), "%Y-%m-%d").date(),
                        amount=Decimal(amt_str.strip()),
                    )
                )

    messages = [m.__dict__ for m in ctx.messages_by_user.get(req.user_id, [])]

    report = analyzer.analyze_plan_resilience(
        state=state,
        plan_payments=tuple(plan_payments),
        unexpected_expense_amount=unexpected_expense,
        user_messages=messages,
    )

    print(f"User: {req.user_id} | Currency: {profile.home_currency} | Balance: {state.available_balance} | Min Keep: {state.minimum_balance_to_keep}")
    print(f"Official Recommendation: {out_row.recommended_payment_method} ({out_row.affordability_status})")
    print(f"Evaluated Plan: {out_row.payment_plan} | Baseline Safe: {'YES' if report.is_baseline_safe else 'NO'} (Margin: {report.baseline_safety_margin})\n")

    print(f"{'STRESS TEST':<35} {'SAFE?':<8} {'LOWEST BAL':<14} {'LOWEST DATE':<14} {'MARGIN':<12} {'DESCRIPTION'}")
    print("-" * 115)

    for res in report.stress_results:
        safe_str = "YES" if res.is_safe else "NO"
        low_date_str = res.lowest_balance_date.isoformat() if res.lowest_balance_date else "-"
        print(
            f"{res.stress_test_name:<35} {safe_str:<8} {str(res.lowest_balance):<14} {low_date_str:<14} "
            f"{str(res.safety_margin):<12} {res.description}"
        )

    print("-" * 115)
    print("NOTE: Resilience analysis is diagnostic and does NOT alter the official challenge output.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Buy or Wait? AI-powered financial decision agent.",
    )
    parser.add_argument(
        "--check-data",
        action="store_true",
        help="Perform comprehensive dataset audit and referential integrity check.",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run full evaluation on requests.csv and generate root output.csv and usage_report.md.",
    )
    parser.add_argument(
        "--time-machine",
        type=str,
        metavar="REQUEST_ID",
        help="Run interactive Financial Time Machine scenario simulation on a specific request_id.",
    )
    parser.add_argument(
        "--resilience-analysis",
        type=str,
        metavar="REQUEST_ID",
        help="Run non-destructive cash flow stress testing and resilience analysis on a specific request_id.",
    )
    parser.add_argument(
        "--unexpected-expense",
        type=Decimal,
        metavar="AMOUNT",
        help="Optional custom unexpected expense amount for resilience analysis stress testing.",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DEFAULT_DATASET_DIR,
        help="Path to dataset directory containing CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "output.csv",
        help="Path to write the output.csv predictions.",
    )

    args = parser.parse_args()

    if args.check_data:
        return run_check_data(args.dataset_dir)

    if args.time_machine:
        return run_time_machine(args.dataset_dir, args.time_machine)

    if args.resilience_analysis:
        return run_resilience_analysis(args.dataset_dir, args.resilience_analysis, args.unexpected_expense)

    # By default or when --evaluate is passed, run the full pipeline
    from evaluation.main import run_evaluation
    return run_evaluation(
        dataset_dir=args.dataset_dir,
        output_path=args.output,
        report_path=REPO_ROOT / "code" / "evaluation" / "usage_report.md",
    )


if __name__ == "__main__":
    sys.exit(main())


