"""Deterministic financial-state reconstruction for Buy or Wait?.

This module deliberately reconstructs facts only.  It does not forecast a
balance, choose a payment method, or write ``output.csv``; those belong to
later phases.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from currency_conversion_service import CurrencyConversionService, MissingExchangeRateError
from message_interpreter import MessageFact, MessageInterpreter
from missing_amount_resolver import ImageBackedMissingAmountResolver, MissingAmountResolver


ZERO = Decimal("0")
_CASH_STATUSES = frozenset({"settled", "scheduled", "pending"})
_EXCLUDED_STATUSES = frozenset({"failed", "cancelled"})


@dataclass(frozen=True)
class NormalizedEvent:
    """A supplied financial event after deterministic evidence resolution."""

    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: Decimal | None
    currency: str
    amount_home_currency: Decimal | None
    conversion_rate: Decimal | None
    conversion_rate_date: date | None
    amount_source: str
    event_date: date
    settlement_date: date | None
    status: str
    linked_event_id: str | None
    flexibility: str
    minimum_allowed_amount: Decimal | None
    financial_meaning: str
    is_recurring: bool
    is_confirmed_income: bool
    is_confirmed_future_payment: bool
    is_refund: bool
    is_transfer: bool
    included_in_cash_state: bool
    exclusion_reason: str | None
    evidence_resolution: str | None


@dataclass(frozen=True)
class FinancialState:
    """All deterministic financial facts for one request and its user."""

    request_id: str
    user_id: str
    request_date: date
    home_currency: str
    available_balance: Decimal
    minimum_balance_to_keep: Decimal
    events: tuple[NormalizedEvent, ...]
    recurring_expenses: tuple[NormalizedEvent, ...]
    one_time_expenses: tuple[NormalizedEvent, ...]
    confirmed_income: tuple[NormalizedEvent, ...]
    confirmed_future_payments: tuple[NormalizedEvent, ...]
    refunds: tuple[NormalizedEvent, ...]
    transfers: tuple[NormalizedEvent, ...]


class FinancialStateService:
    """Loads and reconstructs one user's state from the provided CSV files.

    Conflict precedence is applied only to a demonstrable conflict family:
    exact duplicate records, or linked records with the same event type,
    direction, and category.  A ``linked_event_id`` alone therefore never
    makes an unrelated cash record disappear.
    """

    def __init__(self, dataset_dir: str | Path, missing_amount_resolver: MissingAmountResolver | None = None):
        self.dataset_dir = Path(dataset_dir)
        self._profiles = self._read_csv("financial_profiles.csv")
        self._requests = self._read_csv("requests.csv") + self._read_csv("sample_requests.csv")
        self._events = self._read_csv("financial_events.csv")
        self._messages = self._read_csv("messages.csv")
        self._currency_converter = CurrencyConversionService(self.dataset_dir)
        self._missing_amount_resolver = missing_amount_resolver or ImageBackedMissingAmountResolver(self.dataset_dir)
        self._message_interpreter = MessageInterpreter()

        self._profiles_by_user = self._one_by_key(self._profiles, "user_id")
        self._requests_by_id = self._one_by_key(self._requests, "request_id")
        self._events_by_id = self._one_by_key(self._events, "event_id")
        self._facts_by_event: dict[str, list[MessageFact]] = defaultdict(list)
        for message in self._messages:
            for fact in self._message_interpreter.interpret(message):
                if fact.event_id:
                    self._facts_by_event[fact.event_id].append(fact)

    def reconstruct(self, request_id: str) -> FinancialState:
        """Return a deterministic reconstructed state for ``request_id``.

        Missing images/amounts remain ``None``.  This service never turns a
        missing amount into zero and never manufactures an amount from text.
        """

        request = self._requests_by_id.get(request_id)
        if request is None:
            raise KeyError(f"Unknown request_id: {request_id}")
        user_id = request["user_id"]
        profile = self._profiles_by_user.get(user_id)
        if profile is None:
            raise KeyError(f"No financial profile for user_id: {user_id}")

        request_date = _parse_date(request["request_date"])
        home_currency = profile["home_currency"]
        raw_events = [row for row in self._events if row["user_id"] == user_id]
        selected, duplicate_ids = self._resolve_conflicts(raw_events)
        selected_events = [event for event in raw_events if event["event_id"] in selected]
        recurring_ids = self._recurring_event_ids(selected_events)

        normalized: list[NormalizedEvent] = []
        for event in raw_events:
            # A terminal supplied status takes precedence over the later
            # duplicate/conflict selection.  Preserve its actual reason rather
            # than relabeling a cancelled or failed record as a duplicate.
            if self._effective_status(event) in _EXCLUDED_STATUSES:
                normalized.append(
                    self._normalize(
                        event,
                        request_date,
                        home_currency,
                        is_recurring=False,
                        included=True,
                        exclusion_reason=None,
                        evidence_resolution=self._evidence_resolution(event["event_id"]),
                    )
                )
                continue
            if event["event_id"] in duplicate_ids:
                normalized.append(
                    self._normalize(
                        event,
                        request_date,
                        home_currency,
                        is_recurring=False,
                        included=False,
                        exclusion_reason="duplicate_record",
                        evidence_resolution=None,
                    )
                )
                continue
            if event["event_id"] not in selected:
                # This branch is intentionally defensive; all non-duplicates
                # selected by the conflict resolver are represented below.
                continue
            resolution = self._evidence_resolution(event["event_id"])
            normalized.append(
                self._normalize(
                    event,
                    request_date,
                    home_currency,
                    is_recurring=event["event_id"] in recurring_ids,
                    included=True,
                    exclusion_reason=None,
                    evidence_resolution=resolution,
                )
            )

        normalized.sort(key=lambda item: (item.settlement_date or item.event_date, item.event_id))
        included = tuple(item for item in normalized if item.included_in_cash_state)
        expenses = tuple(item for item in included if item.financial_meaning == "expense")
        return FinancialState(
            request_id=request_id,
            user_id=user_id,
            request_date=request_date,
            home_currency=home_currency,
            available_balance=_decimal(profile["current_available_balance"]),
            minimum_balance_to_keep=_decimal(profile["minimum_balance_to_keep"]),
            events=tuple(normalized),
            recurring_expenses=tuple(item for item in expenses if item.is_recurring),
            one_time_expenses=tuple(item for item in expenses if not item.is_recurring),
            confirmed_income=tuple(item for item in included if item.is_confirmed_income),
            confirmed_future_payments=tuple(item for item in included if item.is_confirmed_future_payment),
            refunds=tuple(item for item in included if item.is_refund),
            transfers=tuple(item for item in included if item.is_transfer),
        )

    def _resolve_conflicts(
        self, events: list[Mapping[str, str]]
    ) -> tuple[set[str], set[str]]:
        """Choose one record in each demonstrable duplicate/conflict family.

        Precedence is: explicit cancellation/settlement/amendment evidence;
        newer record from the same supplied financial-events source; settled
        status; then the financially safer amount/direction interpretation.
        """

        groups: dict[tuple[str, ...], list[Mapping[str, str]]] = defaultdict(list)
        for event in events:
            groups[self._conflict_key(event)].append(event)

        selected: set[str] = set()
        discarded: set[str] = set()
        for group in groups.values():
            if len(group) == 1:
                selected.add(group[0]["event_id"])
                continue
            winner = max(group, key=self._precedence_key)
            selected.add(winner["event_id"])
            discarded.update(item["event_id"] for item in group if item is not winner)
        return selected, discarded

    def _conflict_key(self, event: Mapping[str, str]) -> tuple[str, ...]:
        linked = event["linked_event_id"]
        has_linked_child = any(row["linked_event_id"] == event["event_id"] for row in self._events)
        if (linked and linked in self._events_by_id) or has_linked_child:
            root = self._lifecycle_root(event["event_id"])
            return ("linked", root, event["event_type"], event["direction"], event["category"])
        # Exact same financial fact reported more than once is a duplicate;
        # status and identifier are deliberately excluded from this key.
        return (
            "exact",
            event["event_type"], event["description"], event["category"],
            event["direction"], event["currency"],
            event["event_date"], event["settlement_date"], event["flexibility"],
            event["minimum_allowed_amount"],
            # Independently supplied income entries with different cash states
            # can be distinct payments, even when their other details match.
            # Linked income lifecycle records remain handled by the linked
            # conflict branch above.
            event["status"] if event["event_type"].lower() == "income" else "",
        )

    def _lifecycle_root(self, event_id: str) -> str:
        seen: set[str] = set()
        current = event_id
        while current not in seen:
            seen.add(current)
            parent = self._events_by_id[current]["linked_event_id"]
            if not parent or parent not in self._events_by_id:
                return current
            current = parent
        return min(seen)

    def _precedence_key(self, event: Mapping[str, str]) -> tuple[Decimal | int | date | str, ...]:
        resolution = self._evidence_resolution(event["event_id"])
        # Explicit facts are priority one. Cancellation is deliberately first
        # because it is the least permissive cash interpretation.
        explicit_rank = {"explicit_cancellation": 3, "explicit_settlement": 2, "explicit_amendment": 1}.get(resolution, 0)
        event_day = _parse_date(event["settlement_date"] or event["event_date"])
        settled_rank = 1 if self._effective_status(event) == "settled" else 0
        amount = _optional_decimal(event["amount"]) or ZERO
        # Safer means a larger debit and a smaller credit.  ``max`` selects the
        # value below only after all earlier precedence dimensions tie.
        safety = -amount if event["direction"] == "credit" else amount
        return (explicit_rank, event_day, settled_rank, safety, event["event_id"])

    def _evidence_resolution(self, event_id: str) -> str | None:
        facts = self._facts_by_event[event_id]
        if any(fact.amendment_type == "explicit_cancellation" for fact in facts):
            return "explicit_cancellation"
        if any(fact.amendment_type == "explicit_settlement" for fact in facts):
            return "explicit_settlement"
        if any(fact.amendment_type in {"explicit_amendment", "salary_change", "salary_delay"} for fact in facts):
            return "explicit_amendment"
        return None

    def _effective_status(self, event: Mapping[str, str]) -> str:
        resolution = self._evidence_resolution(event["event_id"])
        if resolution == "explicit_cancellation":
            return "cancelled"
        if resolution == "explicit_settlement":
            return "settled"
        return event["status"].lower()

    def _recurring_event_ids(self, events: Iterable[Mapping[str, str]]) -> set[str]:
        """Mark expenses recurring only with at least three monthly observations."""

        groups: dict[tuple[str, str, str, str], list[Mapping[str, str]]] = defaultdict(list)
        for event in events:
            if event["direction"] != "debit" or event["event_type"] not in {"expense", "subscription", "debt_payment"}:
                continue
            if self._effective_status(event) in _EXCLUDED_STATUSES:
                continue
            groups[(event["event_type"], event["category"], event["currency"], event["description"])].append(event)

        recurring: set[str] = set()
        for group in groups.values():
            ordered = sorted(group, key=lambda item: _parse_date(item["settlement_date"] or item["event_date"]))
            if len(ordered) < 3:
                continue
            dates = [_parse_date(item["settlement_date"] or item["event_date"]) for item in ordered]
            gaps = [(right - left).days for left, right in zip(dates, dates[1:])]
            if gaps and all(25 <= gap <= 35 for gap in gaps):
                recurring.update(item["event_id"] for item in ordered)
        return recurring

    def _normalize(
        self,
        event: Mapping[str, str],
        request_date: date,
        home_currency: str,
        *,
        is_recurring: bool,
        included: bool,
        exclusion_reason: str | None,
        evidence_resolution: str | None,
    ) -> NormalizedEvent:
        status = self._effective_status(event)
        event_type = event["event_type"].lower()
        is_refund = event_type == "refund"
        is_transfer = "transfer" in event["description"].lower() or any(
            fact.amendment_type == "intra_account_transfer" for fact in self._facts_by_event[event["event_id"]]
        )
        meaning = "income" if event_type == "income" else "refund" if is_refund else "transfer" if is_transfer else "expense" if event["direction"] == "debit" else "investment" if event_type.startswith("investment") else "other"

        resolved_amount = self._missing_amount_resolver.resolve(event["event_id"]) if not event["amount"] else None
        amount = resolved_amount.amount if resolved_amount else _optional_decimal(event["amount"])
        amount_source = resolved_amount.source if resolved_amount else "financial_events.csv" if amount is not None else "unresolved"
        settlement_date = _optional_date(event["settlement_date"])
        event_day = _parse_date(event["event_date"])
        rate_date = settlement_date or event_day
        amount_home_currency: Decimal | None = None
        conversion_rate: Decimal | None = None
        if amount is not None:
            try:
                conversion = self._currency_converter.convert(amount, event["currency"], home_currency, rate_date)
                amount_home_currency = conversion.converted_amount
                conversion_rate = conversion.rate
            except MissingExchangeRateError:
                # A missing rate is not a license to derive, invert, or fetch
                # one. The event remains visible but cannot enter cash state.
                pass

        if included:
            if status in _EXCLUDED_STATUSES:
                included, exclusion_reason = False, status
            elif status == "unrealized" or event["direction"] == "non_cash" or event_type == "investment_valuation":
                included, exclusion_reason = False, "unrealized_or_non_cash_investment"
            elif event["direction"] == "credit" and status == "pending":
                included, exclusion_reason = False, "pending_credit"
            elif amount is None:
                included, exclusion_reason = False, "amount_missing_requires_image"
            elif amount_home_currency is None:
                included, exclusion_reason = False, "missing_exchange_rate"
        confirmed_income = included and event_type == "income" and event["direction"] == "credit" and status in {"settled", "scheduled"}
        future_payment = included and event["direction"] == "debit" and status in {"pending", "scheduled"} and (settlement_date or event_day) >= request_date
        return NormalizedEvent(
            event_id=event["event_id"], user_id=event["user_id"], event_type=event_type,
            description=event["description"], category=event["category"], direction=event["direction"],
            amount=amount, currency=event["currency"], amount_home_currency=amount_home_currency,
            conversion_rate=conversion_rate, conversion_rate_date=rate_date, event_date=event_day,
            amount_source=amount_source,
            settlement_date=settlement_date, status=status, linked_event_id=event["linked_event_id"] or None,
            flexibility=event["flexibility"], minimum_allowed_amount=_optional_decimal(event["minimum_allowed_amount"]),
            financial_meaning=meaning, is_recurring=is_recurring, is_confirmed_income=confirmed_income,
            is_confirmed_future_payment=future_payment, is_refund=is_refund, is_transfer=is_transfer,
            included_in_cash_state=included, exclusion_reason=exclusion_reason,
            evidence_resolution=evidence_resolution,
        )

    def _read_csv(self, filename: str) -> list[dict[str, str]]:
        path = self.dataset_dir / filename
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _one_by_key(rows: Iterable[Mapping[str, str]], key: str) -> dict[str, Mapping[str, str]]:
        result: dict[str, Mapping[str, str]] = {}
        for row in rows:
            if row[key] in result:
                raise ValueError(f"Duplicate {key}: {row[key]}")
            result[row[key]] = row
        return result


def _decimal(value: str) -> Decimal:
    return Decimal(value)


def _optional_decimal(value: str) -> Decimal | None:
    return Decimal(value) if value else None


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _optional_date(value: str) -> date | None:
    return _parse_date(value) if value else None
