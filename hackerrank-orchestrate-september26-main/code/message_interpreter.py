"""Deterministic, non-agentic interpretation of supplied financial messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping


_CURRENCIES = frozenset({"USD", "IDR", "INR", "EUR", "ZAR"})
_AMOUNT = re.compile(r"\b(EUR|IDR|INR|USD|ZAR)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\b", re.IGNORECASE)
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Pattern detectors
_CANCEL = re.compile(r"\b(cancelled|canceled|cancel)\b", re.IGNORECASE)
_PENDING_REFUND = re.compile(
    r"\brefund\b.*\b(initiated|processing|pending|not reached|not credited|still|yet)\b",
    re.IGNORECASE,
)
_FOREIGN_SETTLEMENT = re.compile(
    r"\bforeign[ -]currency\b.*\b(settle|settlement|convert|conversion|rate|processing|refund)\b",
    re.IGNORECASE,
)
_DISPUTE = re.compile(
    r"\b(dispute|investigated|investigation|reversal has not been posted|reversal not posted)\b",
    re.IGNORECASE,
)
_INTRA_ACCOUNT_TRANSFER = re.compile(
    r"\b(transfer between your two accounts|matching debit and credit|both accounts are registered)\b",
    re.IGNORECASE,
)
_PENDING_PAYOUT = re.compile(
    r"\b(payout is still pending|isn[’']t withdrawable until|is not withdrawable until|still in payment processing|has not been credited to your account yet)\b",
    re.IGNORECASE,
)
_SALARY = re.compile(r"\b(salary|payroll|gaji|penggajian)\b", re.IGNORECASE)
_SALARY_DELAY = re.compile(
    r"\b(replaces|revised date|expected on|scheduled for|diperkirakan masuk|menggantikan)\b",
    re.IGNORECASE,
)
_SALARY_CHANGE = re.compile(
    r"\b(changed|change applies|increased|reduced|temporary|remaining confirmed|first salary|regular salary|naik|berkurang|gaji pertama)\b",
    re.IGNORECASE,
)
_CONFIRMED = re.compile(r"\b(confirmed|scheduled|expected|approved|disetujui|dikonfirmasi)\b", re.IGNORECASE)
_AMENDMENT = re.compile(r"\b(amended|revised|replaces|replacement|updated amount|changed amount)\b", re.IGNORECASE)
_EXPLICIT_SETTLED = re.compile(
    r"\b((?:proceeds|credit|money|payment|funds)?\s*(?:have|has)?\s*(?:reached your account|settled in the cash account)|has reached your account|reached your account)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MessageFact:
    """A validated financial fact extracted from one message."""

    message_id: str
    event_id: str | None
    status: str | None
    amount: Decimal | None
    currency: str | None
    date: date | None
    amendment_type: str


class MessageInterpreter:
    """Recognize a bounded set of deterministic financial-message patterns."""

    def interpret(self, message: Mapping[str, str]) -> tuple[MessageFact, ...]:
        text = message["message_text"]
        event_id = message.get("related_event_id") or None
        amount, currency = _first_amount(text)
        message_date = _first_date(text)
        message_id = message["message_id"]

        # 1. Intra-account transfer
        if _INTRA_ACCOUNT_TRANSFER.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    None,
                    amount,
                    currency,
                    message_date,
                    "intra_account_transfer",
                ),
            )

        # 2. Explicit cancellation
        if _CANCEL.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "cancelled",
                    amount,
                    currency,
                    message_date,
                    "explicit_cancellation",
                ),
            )

        # 3. Foreign currency settlement
        if _FOREIGN_SETTLEMENT.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "pending",
                    amount,
                    currency,
                    message_date,
                    "foreign_currency_settlement",
                ),
            )

        # 4. Pending refund
        if _PENDING_REFUND.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "pending",
                    amount,
                    currency,
                    message_date,
                    "pending_refund",
                ),
            )

        # 5. Disputed transaction
        if _DISPUTE.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "pending",
                    amount,
                    currency,
                    message_date,
                    "disputed_transaction",
                ),
            )

        # 6. Pending payout / pending prize claim
        if _PENDING_PAYOUT.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "pending",
                    amount,
                    currency,
                    message_date,
                    "pending_credit",
                ),
            )

        # 7. Salary delay
        if _SALARY.search(text) and _SALARY_DELAY.search(text) and message_date is not None:
            status = "scheduled" if _CONFIRMED.search(text) else None
            return (
                self._fact(
                    message_id,
                    event_id,
                    status,
                    amount,
                    currency,
                    message_date,
                    "salary_delay",
                ),
            )

        # 8. Salary change
        if _SALARY.search(text) and _SALARY_CHANGE.search(text):
            status = "scheduled" if _CONFIRMED.search(text) else None
            return (
                self._fact(
                    message_id,
                    event_id,
                    status,
                    amount,
                    currency,
                    message_date,
                    "salary_change",
                ),
            )

        # 9. Explicit settlement
        if _EXPLICIT_SETTLED.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    "settled",
                    amount,
                    currency,
                    message_date,
                    "explicit_settlement",
                ),
            )

        # 10. General explicit amendment
        if _AMENDMENT.search(text):
            return (
                self._fact(
                    message_id,
                    event_id,
                    None,
                    amount,
                    currency,
                    message_date,
                    "explicit_amendment",
                ),
            )

        # Untrusted prompt injection or irrelevant text -> no facts extracted
        return ()

    @staticmethod
    def _fact(
        message_id: str,
        event_id: str | None,
        status: str | None,
        amount: Decimal | None,
        currency: str | None,
        msg_date: date | None,
        amendment_type: str,
    ) -> MessageFact:
        return MessageFact(
            message_id=message_id,
            event_id=event_id,
            status=status,
            amount=amount,
            currency=currency,
            date=msg_date,
            amendment_type=amendment_type,
        )


def _first_amount(text: str) -> tuple[Decimal | None, str | None]:
    match = _AMOUNT.search(text)
    if not match:
        return None, None
    curr = match.group(1).upper()
    raw = match.group(2).replace(",", "")
    try:
        return Decimal(raw), curr
    except (InvalidOperation, TypeError):
        return None, None


def _first_date(text: str) -> date | None:
    match = _DATE.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
