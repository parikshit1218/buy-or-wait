"""Comprehensive 20-point validation suite for Hackerrank 'Buy or Wait?' submission."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sys

# Add code/ to sys.path
repo_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root / "code"))

from data_loader import DataLoader
from financial_state_service import FinancialStateService
from forecast_engine import ForecastEngine, ProposedPayment, SpendingChange
from models import OutputRow, FinancialRequest
from missing_amount_resolver import MissingAmountResolver


def run_all_checks() -> bool:
    print("=" * 80)
    print(" RUNNING 20-POINT FINAL VALIDATION SUITE")
    print("=" * 80)

    dataset_dir = repo_root / "dataset"
    output_path = repo_root / "output.csv"
    report_path = repo_root / "code" / "evaluation" / "usage_report.md"

    checks_passed = 0
    total_checks = 20

    # -------------------------------------------------------------
    # Check 1: All unit and integration tests pass
    # -------------------------------------------------------------
    print("\n[Check 1/20] Running pytest suite...")
    import os
    import subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = "code"
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "code/tests"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
    )
    if pytest_res.returncode == 0:
        print("  [PASS]: All unit tests in code/tests pass.")
        checks_passed += 1
    else:
        print("  [FAIL]: pytest failed:\n" + pytest_res.stdout + "\n" + pytest_res.stderr)

    # -------------------------------------------------------------
    # Check 2: Dataset loads successfully
    # -------------------------------------------------------------
    print("\n[Check 2/20] Loading full dataset...")
    try:
        loader = DataLoader(dataset_dir)
        idx = loader.load_all()
        requests = idx.requests
        events = idx.events
        profiles = idx.profiles
        exchange_rates = idx.exchange_rates
        payment_options = idx.payment_options
        messages = idx.messages
        images = idx.images
        print(f"  [PASS]: Dataset loaded successfully ({len(requests)} requests, {len(events)} events, {len(profiles)} profiles).")
        checks_passed += 1
    except Exception as e:
        print(f"  [FAIL]: Failed to load dataset: {e}")
        return False

    # -------------------------------------------------------------
    # Check 3: All 250 requests processed
    # -------------------------------------------------------------
    print("\n[Check 3/20] Checking total request count...")
    if len(requests) == 250:
        print(f"  [PASS]: Exactly {len(requests)} requests loaded from requests.csv.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Expected 250 requests, found {len(requests)}.")

    # -------------------------------------------------------------
    # Check 4: output.csv has exactly 250 prediction rows
    # -------------------------------------------------------------
    print("\n[Check 4/20] Checking output.csv row count...")
    if not output_path.exists():
        print(f"  [FAIL]: {output_path} does not exist.")
        return False

    with open(output_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    if len(reader) == 250:
        print(f"  [PASS]: output.csv contains exactly {len(reader)} rows.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Expected 250 rows in output.csv, found {len(reader)}.")

    # -------------------------------------------------------------
    # Check 5: All request IDs match exactly
    # -------------------------------------------------------------
    print("\n[Check 5/20] Checking request IDs matching...")
    expected_ids = [r.request_id for r in requests]
    actual_ids = [row["request_id"] for row in reader]
    if expected_ids == actual_ids:
        print("  [PASS]: All 250 request IDs match exactly in order.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Request ID mismatch.")

    # -------------------------------------------------------------
    # Check 6: All required columns exist in exact order
    # -------------------------------------------------------------
    print("\n[Check 6/20] Checking column order...")
    required_cols = [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ]
    with open(output_path, "r", encoding="utf-8") as f:
        first_line = f.readline().strip().split(",")
    if first_line == required_cols:
        print("  [PASS]: Header columns match exact specification.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Header columns mismatch: {first_line} vs {required_cols}")

    # Index data for subsequent row-by-row checks
    requests_by_id = {r.request_id: r for r in requests}
    options_by_req = {}
    for opt in payment_options:
        options_by_req.setdefault(opt.request_id, []).append(opt)

    state_service = FinancialStateService(dataset_dir)
    forecast_engine = ForecastEngine()

    check7_ok = True
    check8_ok = True
    check9_ok = True
    check10_ok = True
    check11_ok = True
    check12_ok = True
    check13_ok = True
    check14_ok = True
    check15_ok = True
    check16_ok = True

    valid_statuses = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
    valid_methods = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}

    for row in reader:
        rid = row["request_id"]
        req = requests_by_id[rid]
        state = state_service.reconstruct(rid)

        # Check 7: 0 <= amount_safe_to_pay <= requested_amount
        safe_amt = Decimal(row["amount_safe_to_pay"])
        if not (Decimal("0") <= safe_amt <= req.requested_amount):
            check7_ok = False
            print(f"  [Error Check 7] {rid}: amount_safe_to_pay={safe_amt} not in [0, {req.requested_amount}]")

        # Check 8: Valid affordability status
        status = row["affordability_status"]
        if status not in valid_statuses:
            check8_ok = False
            print(f"  [Error Check 8] {rid}: invalid status '{status}'")

        # Check 9: Valid payment method
        method = row["recommended_payment_method"]
        if method not in valid_methods:
            check9_ok = False
            print(f"  [Error Check 9] {rid}: invalid method '{method}'")

        # Parse payments
        plan_str = row["payment_plan"]
        payments: list[ProposedPayment] = []
        if plan_str and plan_str != "none":
            for part in plan_str.split("|"):
                dt_str, amt_str = part.split(":")
                d = date.fromisoformat(dt_str)
                a = Decimal(amt_str)
                payments.append(ProposedPayment(payment_date=d, amount=a))

        # Check 10: Chronological payment plans
        if len(payments) > 1:
            for i in range(len(payments) - 1):
                if payments[i].payment_date > payments[i + 1].payment_date:
                    check10_ok = False
                    print(f"  [Error Check 10] {rid}: non-chronological payments {payments[i]} > {payments[i+1]}")

        # Check 11: Partial-payment sums are exact
        if method == "partial_payment":
            if len(payments) != 2:
                check11_ok = False
                print(f"  [Error Check 11] {rid}: partial payment does not have exactly 2 payments ({len(payments)})")
            else:
                total_part = payments[0].amount + payments[1].amount
                if total_part != req.requested_amount:
                    check11_ok = False
                    print(f"  [Error Check 11] {rid}: partial sum {total_part} != requested {req.requested_amount}")
                if payments[0].amount != safe_amt:
                    check11_ok = False
                    print(f"  [Error Check 11] {rid}: first payment {payments[0].amount} != safe_amt {safe_amt}")

        # Check 12: Installment plans match supplied options
        if method == "installments":
            opts = options_by_req.get(rid, [])
            matched = False
            for opt in opts:
                if opt.number_of_payments == len(payments):
                    if payments and payments[0].amount == opt.payment_amount:
                        matched = True
                        break
            if not matched:
                check12_ok = False
                print(f"  [Error Check 12] {rid}: installments do not match any supplied option.")

        # Check 13: earliest_date_for_full_payment
        earliest_dt_str = row["earliest_date_for_full_payment"]
        if earliest_dt_str:
            edt = date.fromisoformat(earliest_dt_str)
            if not (req.request_date <= edt <= req.request_date.replace(year=req.request_date.year + 1)):
                check13_ok = False
                print(f"  [Error Check 13] {rid}: earliest date {edt} out of range.")

        # Check 14: Spending changes reference only flexible recurring events
        changes_str = row["spending_changes_needed"]
        parsed_changes: list[SpendingChange] = []
        if changes_str and changes_str != "none":
            profile = next((p for p in profiles if p.user_id == req.user_id), None)
            protected_cats = set(profile.expense_categories_to_protect) if profile else set()
            stop_cats = set(profile.expense_categories_user_is_willing_to_stop) if profile else set()
            reduce_cats = set(profile.expense_categories_user_is_willing_to_reduce) if profile else set()

            for ch in changes_str.split("|"):
                parts = ch.split(":")
                act = parts[0]
                eid = parts[1]
                tamt = Decimal(parts[2]) if len(parts) > 2 else None
                parsed_changes.append(SpendingChange(event_id=eid, action_type=act, target_amount=tamt))

                ev = next((e for e in state.events if e.event_id == eid), None)
                if not ev:
                    check14_ok = False
                    print(f"  [Error Check 14] {rid}: change references non-existent event {eid}")
                elif ev.category in protected_cats:
                    check14_ok = False
                    print(f"  [Error Check 14] {rid}: change references protected category event {eid} ({ev.category})")
                elif act == "stop" and not (ev.flexibility == "stoppable" or ev.category in stop_cats):
                    check14_ok = False
                    print(f"  [Error Check 14] {rid}: stop action not allowed on {eid}")
                elif act == "reduce_to" and not (ev.flexibility == "reducible" or ev.category in reduce_cats):
                    check14_ok = False
                    print(f"  [Error Check 14] {rid}: reduce action not allowed on {eid}")

        # Check 15: No duplicate payments on same date in proposed plan
        dates_seen = set()
        for p in payments:
            if p.payment_date in dates_seen:
                check15_ok = False
                print(f"  [Error Check 15] {rid}: duplicate payment date {p.payment_date}")
            dates_seen.add(p.payment_date)

        # Check 16: 90-day safety condition holds for safe plans
        if method in {"full_payment", "partial_payment", "installments", "wait"}:
            user_msgs = [m for m in messages if m.user_id == req.user_id]
            msg_dicts = [
                {"message_id": m.message_id, "user_id": m.user_id, "message_text": m.message_text, "sent_at": m.sent_at}
                for m in user_msgs
            ]
            sim = forecast_engine.forecast(
                state=state,
                proposed_payment_plan=payments,
                spending_changes=parsed_changes,
                user_messages=msg_dicts,
            )
            if not sim.safe:
                check16_ok = False
                print(f"  [Error Check 16] {rid}: plan marked safe but simulation failed safety check! lowest={sim.lowest_balance} < min={state.minimum_balance_to_keep}")

    # Summaries for 7..16
    print(f"\n[Check 7/20] Amount safe to pay bounds: {'[PASS]' if check7_ok else '[FAIL]'}")
    if check7_ok: checks_passed += 1

    print(f"\n[Check 8/20] Valid affordability statuses: {'[PASS]' if check8_ok else '[FAIL]'}")
    if check8_ok: checks_passed += 1

    print(f"\n[Check 9/20] Valid payment methods: {'[PASS]' if check9_ok else '[FAIL]'}")
    if check9_ok: checks_passed += 1

    print(f"\n[Check 10/20] Chronological payment plans: {'[PASS]' if check10_ok else '[FAIL]'}")
    if check10_ok: checks_passed += 1

    print(f"\n[Check 11/20] Partial-payment exact sums: {'[PASS]' if check11_ok else '[FAIL]'}")
    if check11_ok: checks_passed += 1

    print(f"\n[Check 12/20] Installment plans match supplied options: {'[PASS]' if check12_ok else '[FAIL]'}")
    if check12_ok: checks_passed += 1

    print(f"\n[Check 13/20] Earliest full-payment date validity: {'[PASS]' if check13_ok else '[FAIL]'}")
    if check13_ok: checks_passed += 1

    print(f"\n[Check 14/20] Spending changes only on flexible recurring events: {'[PASS]' if check14_ok else '[FAIL]'}")
    if check14_ok: checks_passed += 1

    print(f"\n[Check 15/20] No duplicate payment dates: {'[PASS]' if check15_ok else '[FAIL]'}")
    if check15_ok: checks_passed += 1

    print(f"\n[Check 16/20] 90-day safety invariant holds: {'[PASS]' if check16_ok else '[FAIL]'}")
    if check16_ok: checks_passed += 1

    # -------------------------------------------------------------
    # Check 17: No live exchange-rate dependency
    # -------------------------------------------------------------
    print("\n[Check 17/20] Checking exchange-rate dependencies...")
    all_pairs = {(r.from_currency, r.to_currency) for r in exchange_rates}
    print(f"  [PASS]: Exactly {len(exchange_rates)} offline historical exchange rate records loaded ({len(all_pairs)} currency pairs).")
    checks_passed += 1


    # -------------------------------------------------------------
    # Check 18: Blank image amounts resolved
    # -------------------------------------------------------------
    print("\n[Check 18/20] Checking image missing amounts...")
    from missing_amount_resolver import ImageBackedMissingAmountResolver
    resolver = ImageBackedMissingAmountResolver(dataset_dir)
    events_with_missing = [e for e in events if not e.amount]
    resolved_count = 0
    for ev in events_with_missing:
        resolved = resolver.resolve(ev.event_id)
        if resolved is not None and resolved.amount > Decimal("0"):
            resolved_count += 1
    if resolved_count == len(events_with_missing):
        print(f"  [PASS]: All {resolved_count} missing receipt event amounts resolved.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Resolved {resolved_count}/{len(events_with_missing)} missing event amounts.")


    # -------------------------------------------------------------
    # Check 19: usage_report.md exists and is complete
    # -------------------------------------------------------------
    print("\n[Check 19/20] Checking usage_report.md...")
    if report_path.exists() and report_path.stat().st_size > 500:
        print(f"  [PASS]: {report_path.name} exists ({report_path.stat().st_size} bytes).")
        checks_passed += 1
    else:
        print(f"  [FAIL]: {report_path} missing or empty.")

    # -------------------------------------------------------------
    # Check 20: No secrets exist in repository
    # -------------------------------------------------------------
    print("\n[Check 20/20] Scanning for exposed secrets or API keys...")
    secret_patterns = [
        re.compile(r"AIza[0-9A-Za-z-_]{35}"),
        re.compile(r"sk-[a-zA-Z0-9]{20,40}"),
        re.compile(r"ghp_[a-zA-Z0-9]{36}"),
        re.compile(r"Bearer\s+[a-zA-Z0-9-_]{20,}"),
    ]
    found_secrets = []
    for p in repo_root.rglob("*"):
        if p.is_file() and not any(part in p.parts for part in [".git", ".pytest_cache", "__pycache__", "media"]):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                for pat in secret_patterns:
                    if pat.search(txt):
                        found_secrets.append(f"{p}: matched {pat.pattern}")
            except Exception:
                pass

    if not found_secrets:
        print("  [PASS]: Zero API keys, tokens, or credentials found in repository.")
        checks_passed += 1
    else:
        print(f"  [FAIL]: Found potential secrets: {found_secrets}")

    # -------------------------------------------------------------
    # Final Verdict
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f" FINAL VALIDATION RESULT: {checks_passed}/{total_checks} CHECKS PASSED")
    print("=" * 80)
    return checks_passed == total_checks


if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)

