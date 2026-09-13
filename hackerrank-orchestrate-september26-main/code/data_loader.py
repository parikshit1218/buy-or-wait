"""Data loader and reusable relational indexer for Buy or Wait?."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from currency import CurrencyConverter
from models import (
    ExchangeRate,
    FinancialEvent,
    FinancialProfile,
    FinancialRequest,
    ImageRecord,
    Message,
    PaymentOption,
    SampleRequest,
)


def parse_date(value: str) -> date:
    """Safely parse an ISO-8601 date string (YYYY-MM-DD)."""
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def optional_date(value: str | None) -> date | None:
    """Safely parse an optional date string, returning None if empty."""
    return parse_date(value) if value and value.strip() else None


def parse_decimal(value: str) -> Decimal:
    """Safely parse a monetary string into Decimal without float conversion."""
    return Decimal(value.strip().replace(",", ""))


def optional_decimal(value: str | None) -> Decimal | None:
    """Safely parse an optional decimal string, returning None if empty."""
    return parse_decimal(value) if value and value.strip() else None


def parse_bool(value: str) -> bool:
    """Safely parse a boolean string."""
    val = value.strip().lower()
    if val in {"true", "1", "t", "yes"}:
        return True
    if val in {"false", "0", "f", "no"}:
        return False
    raise ValueError(f"Cannot parse boolean from '{value}'")


def parse_pipe_list(value: str | None) -> tuple[str, ...]:
    """Parse pipe-delimited values into a tuple of clean non-empty strings."""
    if not value or not value.strip():
        return ()
    return tuple(item.strip() for item in value.split("|") if item.strip())


def optional_int(value: str | None) -> int | None:
    """Parse an optional integer, returning None if empty."""
    return int(value.strip()) if value and value.strip() else None


@dataclass
class DatasetContext:
    """Fully indexed dataset container providing fast, reusable lookups."""

    # Raw entity collections
    profiles: list[FinancialProfile]
    requests: list[FinancialRequest]
    sample_requests: list[SampleRequest]
    events: list[FinancialEvent]
    payment_options: list[PaymentOption]
    exchange_rates: list[ExchangeRate]
    messages: list[Message]
    images: list[ImageRecord]

    # Indexes by user_id
    profiles_by_user: dict[str, FinancialProfile]
    requests_by_user: dict[str, list[FinancialRequest]]
    events_by_user: dict[str, list[FinancialEvent]]
    messages_by_user: dict[str, list[Message]]
    images_by_user: dict[str, list[ImageRecord]]

    # Indexes by request_id
    requests_by_id: dict[str, FinancialRequest]
    sample_requests_by_id: dict[str, SampleRequest]
    all_requests_by_id: dict[str, FinancialRequest | SampleRequest]
    options_by_request: dict[str, list[PaymentOption]]
    messages_by_request: dict[str, list[Message]]
    images_by_request: dict[str, list[ImageRecord]]

    # Indexes by event_id
    events_by_id: dict[str, FinancialEvent]
    linked_events_by_parent: dict[str, list[FinancialEvent]]

    # Indexes by payment_option_id
    options_by_id: dict[str, PaymentOption]

    # Indexes by image_id
    images_by_id: dict[str, ImageRecord]

    # Indexes by related_event_id
    messages_by_related_event: dict[str, list[Message]]
    images_by_related_event: dict[str, ImageRecord]

    # Currency conversion engine
    currency_converter: CurrencyConverter


class DataLoader:
    """Loads all CSV tables from dataset/ and builds reusable relational indexes."""

    def __init__(self, dataset_dir: str | Path):
        self.dataset_dir = Path(dataset_dir)
        if not self.dataset_dir.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {self.dataset_dir}")

    def load_profiles(self) -> list[FinancialProfile]:
        path = self.dataset_dir / "financial_profiles.csv"
        rows = self._read_csv(path)
        profiles: list[FinancialProfile] = []
        for r in rows:
            profiles.append(
                FinancialProfile(
                    user_id=r["user_id"].strip(),
                    home_currency=r["home_currency"].strip().upper(),
                    current_available_balance=parse_decimal(r["current_available_balance"]),
                    minimum_balance_to_keep=parse_decimal(r["minimum_balance_to_keep"]),
                    financial_priorities=parse_pipe_list(r.get("financial_priorities")),
                    expense_categories_to_protect=parse_pipe_list(r.get("expense_categories_to_protect")),
                    expense_categories_user_is_willing_to_reduce=parse_pipe_list(
                        r.get("expense_categories_user_is_willing_to_reduce")
                    ),
                    expense_categories_user_is_willing_to_stop=parse_pipe_list(
                        r.get("expense_categories_user_is_willing_to_stop")
                    ),
                    payment_methods_user_will_consider=parse_pipe_list(
                        r.get("payment_methods_user_will_consider")
                    ),
                    max_installment_months=optional_int(r.get("max_installment_months")),
                )
            )
        return profiles

    def load_requests(self) -> list[FinancialRequest]:
        path = self.dataset_dir / "requests.csv"
        rows = self._read_csv(path)
        requests: list[FinancialRequest] = []
        for r in rows:
            requests.append(
                FinancialRequest(
                    request_id=r["request_id"].strip(),
                    user_id=r["user_id"].strip(),
                    request_date=parse_date(r["request_date"]),
                    request_type=r["request_type"].strip(),
                    requested_amount=parse_decimal(r["requested_amount"]),
                    desired_completion_date=parse_date(r["desired_completion_date"]),
                    allows_partial_payment=parse_bool(r["allows_partial_payment"]),
                    request_text=r.get("request_text", "").strip(),
                )
            )
        return requests

    def load_sample_requests(self) -> list[SampleRequest]:
        path = self.dataset_dir / "sample_requests.csv"
        rows = self._read_csv(path)
        samples: list[SampleRequest] = []
        for r in rows:
            samples.append(
                SampleRequest(
                    request_id=r["request_id"].strip(),
                    user_id=r["user_id"].strip(),
                    request_date=parse_date(r["request_date"]),
                    request_type=r["request_type"].strip(),
                    requested_amount=parse_decimal(r["requested_amount"]),
                    desired_completion_date=parse_date(r["desired_completion_date"]),
                    allows_partial_payment=parse_bool(r["allows_partial_payment"]),
                    request_text=r.get("request_text", "").strip(),
                    amount_safe_to_pay=parse_decimal(r["amount_safe_to_pay"]),
                    affordability_status=r["affordability_status"].strip(),
                    recommended_payment_method=r["recommended_payment_method"].strip(),
                    payment_plan=r.get("payment_plan", "").strip(),
                    earliest_date_for_full_payment=optional_date(r.get("earliest_date_for_full_payment")),
                    spending_changes_needed=r.get("spending_changes_needed", "").strip(),
                    decision_explanation=r.get("decision_explanation", "").strip(),
                )
            )
        return samples

    def load_events(self) -> list[FinancialEvent]:
        path = self.dataset_dir / "financial_events.csv"
        rows = self._read_csv(path)
        events: list[FinancialEvent] = []
        for r in rows:
            events.append(
                FinancialEvent(
                    event_id=r["event_id"].strip(),
                    user_id=r["user_id"].strip(),
                    event_type=r["event_type"].strip(),
                    description=r.get("description", "").strip(),
                    category=r.get("category", "").strip(),
                    direction=r["direction"].strip(),
                    amount=optional_decimal(r.get("amount")),
                    currency=r["currency"].strip().upper(),
                    event_date=parse_date(r["event_date"]),
                    settlement_date=optional_date(r.get("settlement_date")),
                    status=r["status"].strip(),
                    linked_event_id=r.get("linked_event_id", "").strip() or None,
                    flexibility=r.get("flexibility", "fixed").strip(),
                    minimum_allowed_amount=optional_decimal(r.get("minimum_allowed_amount")),
                )
            )
        return events

    def load_payment_options(self) -> list[PaymentOption]:
        path = self.dataset_dir / "request_payment_options.csv"
        rows = self._read_csv(path)
        options: list[PaymentOption] = []
        for r in rows:
            options.append(
                PaymentOption(
                    payment_option_id=r["payment_option_id"].strip(),
                    request_id=r["request_id"].strip(),
                    payment_method=r["payment_method"].strip(),
                    payment_amount=parse_decimal(r["payment_amount"]),
                    number_of_payments=int(r["number_of_payments"].strip()),
                    first_payment_date=parse_date(r["first_payment_date"]),
                    payment_frequency_days=optional_int(r.get("payment_frequency_days")),
                    financing_fee=parse_decimal(r["financing_fee"]),
                    total_payable_amount=parse_decimal(r["total_payable_amount"]),
                )
            )
        return options

    def load_exchange_rates(self) -> list[ExchangeRate]:
        path = self.dataset_dir / "exchange_rates.csv"
        rows = self._read_csv(path)
        rates: list[ExchangeRate] = []
        for r in rows:
            rates.append(
                ExchangeRate(
                    rate_date=parse_date(r["rate_date"]),
                    from_currency=r["from_currency"].strip().upper(),
                    to_currency=r["to_currency"].strip().upper(),
                    rate=parse_decimal(r["rate"]),
                )
            )
        return rates

    def load_messages(self) -> list[Message]:
        path = self.dataset_dir / "messages.csv"
        rows = self._read_csv(path)
        messages: list[Message] = []
        for r in rows:
            messages.append(
                Message(
                    message_id=r["message_id"].strip(),
                    user_id=r["user_id"].strip(),
                    request_id=r.get("request_id", "").strip() or None,
                    related_event_id=r.get("related_event_id", "").strip() or None,
                    sent_at=r.get("sent_at", "").strip(),
                    source_type=r.get("source_type", "").strip(),
                    message_text=r.get("message_text", "").strip(),
                )
            )
        return messages

    def load_images(self) -> list[ImageRecord]:
        path = self.dataset_dir / "images.csv"
        rows = self._read_csv(path)
        images: list[ImageRecord] = []
        for r in rows:
            images.append(
                ImageRecord(
                    image_id=r["image_id"].strip(),
                    user_id=r["user_id"].strip(),
                    request_id=r["request_id"].strip(),
                    related_event_id=r["related_event_id"].strip(),
                )
            )
        return images

    def load_all(self) -> DatasetContext:
        """Load all files and construct comprehensive indexes."""
        profiles = self.load_profiles()
        requests = self.load_requests()
        sample_requests = self.load_sample_requests()
        events = self.load_events()
        options = self.load_payment_options()
        rates = self.load_exchange_rates()
        messages = self.load_messages()
        images = self.load_images()

        # Indexes by user_id
        profiles_by_user = {p.user_id: p for p in profiles}
        requests_by_user: dict[str, list[FinancialRequest]] = defaultdict(list)
        for req in requests:
            requests_by_user[req.user_id].append(req)

        events_by_user: dict[str, list[FinancialEvent]] = defaultdict(list)
        for ev in events:
            events_by_user[ev.user_id].append(ev)

        messages_by_user: dict[str, list[Message]] = defaultdict(list)
        for msg in messages:
            messages_by_user[msg.user_id].append(msg)

        images_by_user: dict[str, list[ImageRecord]] = defaultdict(list)
        for img in images:
            images_by_user[img.user_id].append(img)

        # Indexes by request_id
        requests_by_id = {req.request_id: req for req in requests}
        sample_requests_by_id = {s.request_id: s for s in sample_requests}
        all_requests_by_id: dict[str, FinancialRequest | SampleRequest] = {}
        all_requests_by_id.update(requests_by_id)
        all_requests_by_id.update(sample_requests_by_id)

        options_by_request: dict[str, list[PaymentOption]] = defaultdict(list)
        for opt in options:
            options_by_request[opt.request_id].append(opt)

        messages_by_request: dict[str, list[Message]] = defaultdict(list)
        for msg in messages:
            if msg.request_id:
                messages_by_request[msg.request_id].append(msg)

        images_by_request: dict[str, list[ImageRecord]] = defaultdict(list)
        for img in images:
            images_by_request[img.request_id].append(img)

        # Indexes by event_id
        events_by_id = {ev.event_id: ev for ev in events}
        linked_events_by_parent: dict[str, list[FinancialEvent]] = defaultdict(list)
        for ev in events:
            if ev.linked_event_id:
                linked_events_by_parent[ev.linked_event_id].append(ev)

        # Indexes by payment_option_id
        options_by_id = {opt.payment_option_id: opt for opt in options}

        # Indexes by image_id
        images_by_id = {img.image_id: img for img in images}

        # Indexes by related_event_id
        messages_by_related_event: dict[str, list[Message]] = defaultdict(list)
        for msg in messages:
            if msg.related_event_id:
                messages_by_related_event[msg.related_event_id].append(msg)

        images_by_related_event = {img.related_event_id: img for img in images}

        # Currency converter
        currency_converter = CurrencyConverter(rates=rates)

        return DatasetContext(
            profiles=profiles,
            requests=requests,
            sample_requests=sample_requests,
            events=events,
            payment_options=options,
            exchange_rates=rates,
            messages=messages,
            images=images,
            profiles_by_user=profiles_by_user,
            requests_by_user=dict(requests_by_user),
            events_by_user=dict(events_by_user),
            messages_by_user=dict(messages_by_user),
            images_by_user=dict(images_by_user),
            requests_by_id=requests_by_id,
            sample_requests_by_id=sample_requests_by_id,
            all_requests_by_id=all_requests_by_id,
            options_by_request=dict(options_by_request),
            messages_by_request=dict(messages_by_request),
            images_by_request=dict(images_by_request),
            events_by_id=events_by_id,
            linked_events_by_parent=dict(linked_events_by_parent),
            options_by_id=options_by_id,
            images_by_id=images_by_id,
            messages_by_related_event=dict(messages_by_related_event),
            images_by_related_event=images_by_related_event,
            currency_converter=currency_converter,
        )

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        if not path.is_file():
            raise FileNotFoundError(f"Required CSV file missing: {path}")
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

