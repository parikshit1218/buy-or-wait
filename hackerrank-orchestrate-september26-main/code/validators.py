"""Data validation and integrity auditing for Buy or Wait?."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from config import SUPPORTED_CURRENCIES
from data_loader import DatasetContext


@dataclass
class ValidationReport:
    """Detailed results of dataset validation."""

    total_requests: int = 0
    total_samples: int = 0
    total_profiles: int = 0
    total_events: int = 0
    total_options: int = 0
    total_messages: int = 0
    total_images: int = 0
    blank_event_amounts: int = 0
    blank_event_ids: list[str] = field(default_factory=list)
    currencies: set[str] = field(default_factory=set)
    missing_joins: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and sum(self.missing_joins.values()) == 0


def validate_dataset(ctx: DatasetContext, media_dir: Path | None = None) -> ValidationReport:
    """Perform comprehensive data integrity and referential checks."""
    report = ValidationReport()

    # 1. Entity counts
    report.total_requests = len(ctx.requests)
    report.total_samples = len(ctx.sample_requests)
    report.total_profiles = len(ctx.profiles)
    report.total_events = len(ctx.events)
    report.total_options = len(ctx.payment_options)
    report.total_messages = len(ctx.messages)
    report.total_images = len(ctx.images)

    # 2. Currencies observed
    profile_currencies = {p.home_currency for p in ctx.profiles}
    event_currencies = {e.currency for e in ctx.events}
    report.currencies = profile_currencies.union(event_currencies)

    for curr in profile_currencies:
        if curr not in SUPPORTED_CURRENCIES:
            report.errors.append(f"Unsupported profile currency: {curr}")

    # 3. Blank amounts check
    blank_events = [e for e in ctx.events if e.amount is None]
    report.blank_event_amounts = len(blank_events)
    report.blank_event_ids = [e.event_id for e in blank_events]

    # Every blank event must be mapped in images.csv
    for e in blank_events:
        if e.event_id not in ctx.images_by_related_event:
            report.errors.append(f"Event {e.event_id} has blank amount but no images.csv mapping")

    # If media_dir provided, check image file existence
    if media_dir is not None:
        for img in ctx.images:
            img_file = media_dir / f"{img.image_id}.png"
            if not img_file.is_file():
                report.errors.append(f"Image evidence file missing: {img_file}")

    # 4. Referential Integrity & Joins
    profile_users = set(ctx.profiles_by_user.keys())
    all_request_ids = set(ctx.all_requests_by_id.keys())
    all_event_ids = set(ctx.events_by_id.keys())

    missing_joins: dict[str, int] = {
        "requests -> profile": 0,
        "sample_requests -> profile": 0,
        "events -> profile": 0,
        "payment_options -> request": 0,
        "messages -> profile": 0,
        "messages -> request": 0,
        "messages -> event": 0,
        "images -> profile": 0,
        "images -> request": 0,
        "images -> event": 0,
        "linked_events -> event": 0,
    }

    # Requests -> Profile
    for req in ctx.requests:
        if req.user_id not in profile_users:
            missing_joins["requests -> profile"] += 1
            report.errors.append(f"Request {req.request_id} has unknown user_id: {req.user_id}")

    # Sample Requests -> Profile
    for s in ctx.sample_requests:
        if s.user_id not in profile_users:
            missing_joins["sample_requests -> profile"] += 1
            report.errors.append(f"Sample {s.request_id} has unknown user_id: {s.user_id}")

    # Events -> Profile
    for ev in ctx.events:
        if ev.user_id not in profile_users:
            missing_joins["events -> profile"] += 1
            report.errors.append(f"Event {ev.event_id} has unknown user_id: {ev.user_id}")

    # Payment Options -> Request
    for opt in ctx.payment_options:
        if opt.request_id not in all_request_ids:
            missing_joins["payment_options -> request"] += 1
            report.errors.append(f"Payment option {opt.payment_option_id} has unknown request_id: {opt.request_id}")

    # Messages -> Profile / Request / Event
    for msg in ctx.messages:
        if msg.user_id not in profile_users:
            missing_joins["messages -> profile"] += 1
            report.errors.append(f"Message {msg.message_id} has unknown user_id: {msg.user_id}")
        if msg.request_id and msg.request_id not in all_request_ids:
            missing_joins["messages -> request"] += 1
            report.errors.append(f"Message {msg.message_id} references unknown request_id: {msg.request_id}")
        if msg.related_event_id and msg.related_event_id not in all_event_ids:
            missing_joins["messages -> event"] += 1
            report.errors.append(f"Message {msg.message_id} references unknown event_id: {msg.related_event_id}")

    # Images -> Profile / Request / Event
    for img in ctx.images:
        if img.user_id not in profile_users:
            missing_joins["images -> profile"] += 1
            report.errors.append(f"Image {img.image_id} has unknown user_id: {img.user_id}")
        if img.request_id not in all_request_ids:
            missing_joins["images -> request"] += 1
            report.errors.append(f"Image {img.image_id} has unknown request_id: {img.request_id}")
        if img.related_event_id not in all_event_ids:
            missing_joins["images -> event"] += 1
            report.errors.append(f"Image {img.image_id} has unknown event_id: {img.related_event_id}")

    # Linked Events -> Event
    for ev in ctx.events:
        if ev.linked_event_id and ev.linked_event_id not in all_event_ids:
            missing_joins["linked_events -> event"] += 1
            report.errors.append(f"Event {ev.event_id} has unresolvable linked_event_id: {ev.linked_event_id}")

    report.missing_joins = missing_joins

    # 5. Financial Bounds & Sanity Checks
    for p in ctx.profiles:
        if p.minimum_balance_to_keep < Decimal("0"):
            report.warnings.append(f"User {p.user_id} has negative minimum balance: {p.minimum_balance_to_keep}")

    for r in ctx.requests:
        if r.requested_amount <= Decimal("0"):
            report.errors.append(f"Request {r.request_id} has non-positive requested amount: {r.requested_amount}")

    return report


def validate_output_file(output_path: Path, expected_request_ids: Sequence[str] = ()) -> ValidationReport:
    """Validate that output.csv meets all challenge constraints and schemas."""
    import csv
    from datetime import datetime
    from config import AFFORDABILITY_STATUSES, RECOMMENDED_PAYMENT_METHODS, OUTPUT_COLUMNS

    report = ValidationReport()
    if not output_path.is_file():
        report.errors.append(f"Output file does not exist: {output_path}")
        return report

    with open(output_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if list(fieldnames) != list(OUTPUT_COLUMNS):
            report.errors.append(f"Output columns mismatch. Expected: {OUTPUT_COLUMNS}, Got: {fieldnames}")

        rows = list(reader)

    report.total_requests = len(rows)
    if expected_request_ids and len(rows) != len(expected_request_ids):
        report.errors.append(f"Row count mismatch: expected {len(expected_request_ids)}, got {len(rows)}")

    seen_ids: set[str] = set()
    for idx, row in enumerate(rows, start=1):
        req_id = row.get("request_id", "").strip()
        if not req_id:
            report.errors.append(f"Row {idx}: missing request_id")
            continue
        if req_id in seen_ids:
            report.errors.append(f"Row {idx}: duplicate request_id {req_id}")
        seen_ids.add(req_id)

        # Status validation
        status = row.get("affordability_status", "").strip()
        if status not in AFFORDABILITY_STATUSES:
            report.errors.append(f"Row {idx} ({req_id}): invalid affordability_status '{status}'")

        # Method validation
        method = row.get("recommended_payment_method", "").strip()
        if method not in RECOMMENDED_PAYMENT_METHODS:
            report.errors.append(f"Row {idx} ({req_id}): invalid recommended_payment_method '{method}'")

        # Amount validation
        amount_str = row.get("amount_safe_to_pay", "").strip()
        try:
            amt = Decimal(amount_str)
            if amt < Decimal("0"):
                report.errors.append(f"Row {idx} ({req_id}): negative amount_safe_to_pay '{amount_str}'")
        except Exception:
            report.errors.append(f"Row {idx} ({req_id}): invalid decimal amount_safe_to_pay '{amount_str}'")

        # Payment plan validation
        plan_str = row.get("payment_plan", "").strip()
        if plan_str != "none":
            for part in plan_str.split("|"):
                if ":" not in part:
                    report.errors.append(f"Row {idx} ({req_id}): malformed payment item '{part}' in plan '{plan_str}'")
                    continue
                d_str, p_amt_str = part.split(":", 1)
                try:
                    datetime.strptime(d_str.strip(), "%Y-%m-%d")
                except Exception:
                    report.errors.append(f"Row {idx} ({req_id}): invalid date '{d_str}' in plan '{plan_str}'")
                try:
                    p_amt = Decimal(p_amt_str.strip())
                    if p_amt <= Decimal("0"):
                        report.errors.append(f"Row {idx} ({req_id}): non-positive payment amount '{p_amt_str}' in plan")
                except Exception:
                    report.errors.append(f"Row {idx} ({req_id}): invalid payment amount '{p_amt_str}' in plan")

        # Earliest date validation
        earliest_str = row.get("earliest_date_for_full_payment", "").strip()
        if earliest_str:
            try:
                datetime.strptime(earliest_str, "%Y-%m-%d")
            except Exception:
                report.errors.append(f"Row {idx} ({req_id}): invalid earliest_date_for_full_payment '{earliest_str}'")

        # Spending changes validation
        changes_str = row.get("spending_changes_needed", "").strip()
        if changes_str != "none":
            changes = changes_str.split("|")
            if len(changes) > 3:
                report.errors.append(f"Row {idx} ({req_id}): more than 3 spending changes '{changes_str}'")
            for c in changes:
                if not (c.startswith("stop:") or c.startswith("reduce_to:")):
                    report.errors.append(f"Row {idx} ({req_id}): invalid spending change format '{c}'")

        # Explanation validation
        explanation = row.get("decision_explanation", "").strip()
        if not explanation:
            report.errors.append(f"Row {idx} ({req_id}): empty decision_explanation")

    if expected_request_ids:
        missing_ids = set(expected_request_ids) - seen_ids
        if missing_ids:
            report.errors.append(f"Missing expected request IDs: {sorted(missing_ids)[:10]}")

    return report


