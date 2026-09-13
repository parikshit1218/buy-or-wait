import csv
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_state_service import FinancialStateService
from missing_amount_resolver import MissingAmountResolver, ResolvedAmount


EVENT_COLUMNS = [
    "event_id", "user_id", "event_type", "description", "category", "direction",
    "amount", "currency", "event_date", "settlement_date", "status", "linked_event_id",
    "flexibility", "minimum_allowed_amount",
]


class FixedMissingAmountResolver(MissingAmountResolver):
    def resolve(self, event_id):
        if event_id != "image_backed":
            return None
        return ResolvedAmount(
            event_id="image_backed", image_id="image_test", image_path=Path("image_test.png"),
            amount=Decimal("321.09"), source="mocked_image_extractor",
        )


class FinancialStateServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dataset = Path(self.temp_dir.name)
        self._write_base_files()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_base_files(self, events=(), messages=(), rates=()):
        self._write_csv("exchange_rates.csv", ["rate_date", "from_currency", "to_currency", "rate"], rates)
        self._write_csv("images.csv", ["image_id", "user_id", "request_id", "related_event_id"], [])
        self._write_csv(
            "financial_profiles.csv",
            ["user_id", "home_currency", "current_available_balance", "minimum_balance_to_keep",
             "financial_priorities", "expense_categories_to_protect",
             "expense_categories_user_is_willing_to_reduce", "expense_categories_user_is_willing_to_stop",
             "payment_methods_user_will_consider", "max_installment_months"],
            [["u1", "USD", "1000.25", "250.00", "emergency_savings", "housing", "dining", "streaming", "full_payment", ""]],
        )
        request_header = ["request_id", "user_id", "request_date", "request_type", "requested_amount", "desired_completion_date", "allows_partial_payment", "request_text"]
        self._write_csv("requests.csv", request_header, [["r1", "u1", "2026-01-10", "purchase", "100", "2026-02-01", "true", "test"]])
        self._write_csv("sample_requests.csv", request_header, [])
        self._write_csv("financial_events.csv", EVENT_COLUMNS, events)
        self._write_csv("messages.csv", ["message_id", "user_id", "request_id", "related_event_id", "sent_at", "source_type", "message_text"], messages)

    def _write_csv(self, name, header, rows):
        with (self.dataset / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    @staticmethod
    def event(event_id, *, event_type="expense", description="bill", category="utilities", direction="debit", amount="100", event_date="2026-01-15", settlement_date="2026-01-15", status="scheduled", linked_event_id="", flexibility="fixed", minimum_allowed_amount=""):
        return [event_id, "u1", event_type, description, category, direction, amount, "USD", event_date, settlement_date, status, linked_event_id, flexibility, minimum_allowed_amount]

    def state(self, events=(), messages=(), rates=(), missing_amount_resolver=None):
        self._write_base_files(events, messages, rates)
        return FinancialStateService(self.dataset, missing_amount_resolver=missing_amount_resolver).reconstruct("r1")

    def test_loads_profile_home_currency_and_decimal_balances(self):
        state = self.state()
        self.assertEqual("u1", state.user_id)
        self.assertEqual("USD", state.home_currency)
        self.assertEqual(Decimal("1000.25"), state.available_balance)
        self.assertEqual(Decimal("250.00"), state.minimum_balance_to_keep)
        self.assertEqual(date(2026, 1, 10), state.request_date)

    def test_classifies_supported_monthly_expenses_as_recurring(self):
        events = [
            self.event("e1", description="Monthly internet", event_date="2025-10-15", settlement_date="2025-10-15", status="settled"),
            self.event("e2", description="Monthly internet", event_date="2025-11-15", settlement_date="2025-11-15", status="settled"),
            self.event("e3", description="Monthly internet", event_date="2025-12-15", settlement_date="2025-12-15", status="settled"),
            self.event("e4", description="One-off repair", event_date="2026-01-16", settlement_date="2026-01-16"),
        ]
        state = self.state(events)
        self.assertEqual({"e1", "e2", "e3"}, {item.event_id for item in state.recurring_expenses})
        self.assertEqual({"e4"}, {item.event_id for item in state.one_time_expenses})

    def test_identifies_settled_and_scheduled_income_but_not_pending_credit(self):
        events = [
            self.event("salary_settled", event_type="income", category="salary", direction="credit", amount="900", status="settled"),
            self.event("salary_scheduled", event_type="income", category="salary", direction="credit", amount="900", settlement_date="2026-01-15", status="scheduled"),
            self.event("commission_pending", event_type="income", category="salary", direction="credit", amount="100", status="pending"),
        ]
        state = self.state(events)
        self.assertEqual({"salary_settled", "salary_scheduled"}, {item.event_id for item in state.confirmed_income})
        pending = next(item for item in state.events if item.event_id == "commission_pending")
        self.assertFalse(pending.included_in_cash_state)
        self.assertEqual("pending_credit", pending.exclusion_reason)

    def test_identifies_confirmed_future_debits(self):
        events = [
            self.event("pending_debit", settlement_date="2026-01-11", status="pending"),
            self.event("scheduled_debit", settlement_date="2026-01-20", status="scheduled"),
            self.event("past_debit", settlement_date="2026-01-01", status="scheduled"),
        ]
        state = self.state(events)
        self.assertEqual({"pending_debit", "scheduled_debit"}, {item.event_id for item in state.confirmed_future_payments})

    def test_identifies_refunds_and_transfers_without_treating_them_as_income(self):
        events = [
            self.event("refund", event_type="refund", direction="credit", amount="25", status="settled"),
            self.event("transfer", description="Transfer to savings account", direction="debit", amount="50", status="settled"),
        ]
        state = self.state(events)
        self.assertEqual(("refund",), tuple(item.event_id for item in state.refunds))
        self.assertEqual(("transfer",), tuple(item.event_id for item in state.transfers))
        self.assertEqual("refund", next(item for item in state.events if item.event_id == "refund").financial_meaning)

    def test_excludes_failed_cancelled_unrealized_and_non_cash_investments(self):
        events = [
            self.event("failed", status="failed"),
            self.event("cancelled", status="cancelled"),
            self.event("unrealized", event_type="investment_valuation", direction="non_cash", status="unrealized"),
        ]
        state = self.state(events)
        reasons = {item.event_id: item.exclusion_reason for item in state.events}
        self.assertEqual("failed", reasons["failed"])
        self.assertEqual("cancelled", reasons["cancelled"])
        self.assertEqual("unrealized_or_non_cash_investment", reasons["unrealized"])

    def test_excludes_duplicate_records(self):
        events = [self.event("duplicate_a"), self.event("duplicate_b")]
        state = self.state(events)
        excluded = [item for item in state.events if item.exclusion_reason == "duplicate_record"]
        self.assertEqual(1, len(excluded))
        self.assertEqual(1, len([item for item in state.events if item.included_in_cash_state]))

    def test_preserves_blank_amount_as_missing_and_excludes_it_pending_image_extraction(self):
        state = self.state([self.event("image_backed", amount="")])
        item = state.events[0]
        self.assertIsNone(item.amount)
        self.assertFalse(item.included_in_cash_state)
        self.assertEqual("amount_missing_requires_image", item.exclusion_reason)

    def test_stores_mock_resolved_image_amount_as_decimal(self):
        state = self.state(
            [self.event("image_backed", amount="")],
            missing_amount_resolver=FixedMissingAmountResolver(),
        )
        item = state.events[0]
        self.assertEqual(Decimal("321.09"), item.amount)
        self.assertEqual(Decimal("321.09"), item.amount_home_currency)
        self.assertEqual("mocked_image_extractor", item.amount_source)
        self.assertTrue(item.included_in_cash_state)

    def test_excludes_foreign_currency_event_when_exact_rate_is_missing(self):
        foreign_event = self.event("foreign", amount="10")
        foreign_event[7] = "EUR"
        state = self.state([foreign_event])
        item = state.events[0]
        self.assertIsNone(item.amount_home_currency)
        self.assertFalse(item.included_in_cash_state)
        self.assertEqual("missing_exchange_rate", item.exclusion_reason)

    def test_normalizes_foreign_event_to_home_currency_using_settlement_date_rate(self):
        foreign_event = self.event("foreign", amount="12.345")
        foreign_event[7] = "EUR"
        state = self.state(
            [foreign_event],
            rates=[["2026-01-15", "EUR", "USD", "1.09"]],
        )
        item = state.events[0]
        self.assertTrue(item.included_in_cash_state)
        self.assertEqual(Decimal("1.09"), item.conversion_rate)
        self.assertEqual(date(2026, 1, 15), item.conversion_rate_date)
        self.assertEqual(Decimal("13.45605"), item.amount_home_currency)

    def test_explicit_cancellation_overrides_event_status(self):
        messages = [["m1", "u1", "", "e1", "2026-01-09T00:00:00Z", "merchant", "The payment was cancelled."]]
        state = self.state([self.event("e1", status="scheduled")], messages)
        item = state.events[0]
        self.assertEqual("cancelled", item.status)
        self.assertEqual("explicit_cancellation", item.evidence_resolution)
        self.assertFalse(item.included_in_cash_state)

    def test_explicit_settlement_overrides_pending_credit(self):
        messages = [["m1", "u1", "", "e1", "2026-01-09T00:00:00Z", "bank", "The credit has reached your account."]]
        state = self.state([self.event("e1", event_type="income", direction="credit", status="pending")], messages)
        item = state.events[0]
        self.assertEqual("settled", item.status)
        self.assertTrue(item.included_in_cash_state)
        self.assertEqual("explicit_settlement", item.evidence_resolution)

    def test_explicit_amendment_precedes_newer_record(self):
        events = [
            self.event("old", amount="50", event_date="2026-01-20", settlement_date="2026-01-20"),
            self.event("amended", amount="75", event_date="2026-01-15", settlement_date="2026-01-15", linked_event_id="old"),
        ]
        messages = [["m1", "u1", "", "amended", "2026-01-09T00:00:00Z", "merchant", "The amount was amended."]]
        state = self.state(events, messages)
        included = [item.event_id for item in state.events if item.included_in_cash_state]
        self.assertEqual(["amended"], included)

    def test_newer_same_source_record_precedes_settled_older_record(self):
        events = [
            self.event("old_settled", amount="50", event_date="2026-01-15", settlement_date="2026-01-15", status="settled"),
            self.event("new_scheduled", amount="75", event_date="2026-01-20", settlement_date="2026-01-20", status="scheduled", linked_event_id="old_settled"),
        ]
        state = self.state(events)
        self.assertEqual(["new_scheduled"], [item.event_id for item in state.events if item.included_in_cash_state])

    def test_settled_then_financially_safer_precedence(self):
        settled_state = self.state([
            self.event("scheduled", status="scheduled"),
            self.event("settled", status="settled"),
        ])
        self.assertEqual(["settled"], [item.event_id for item in settled_state.events if item.included_in_cash_state])

        safer_credit_state = self.state([
            self.event("credit_high", event_type="income", direction="credit", amount="100", status="scheduled"),
            self.event("credit_low", event_type="income", direction="credit", amount="40", status="scheduled"),
        ])
        self.assertEqual(["credit_low"], [item.event_id for item in safer_credit_state.events if item.included_in_cash_state])

        safer_debit_state = self.state([
            self.event("debit_low", event_type="expense", direction="debit", amount="40", status="scheduled"),
            self.event("debit_high", event_type="expense", direction="debit", amount="100", status="scheduled"),
        ])
        self.assertEqual(["debit_high"], [item.event_id for item in safer_debit_state.events if item.included_in_cash_state])

    def test_unknown_request_or_profile_raises_key_error(self):
        service = FinancialStateService(self.dataset)
        with self.assertRaises(KeyError):
            service.reconstruct("unknown_request_999")


if __name__ == "__main__":
    unittest.main()
