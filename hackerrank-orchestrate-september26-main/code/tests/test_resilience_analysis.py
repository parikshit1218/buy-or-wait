"""Unit tests for the Resilience Analysis stress-testing layer."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_state_service import FinancialState, NormalizedEvent
from forecast_engine import ForecastEngine, ProposedPayment
from resilience_analysis import ResilienceAnalyzer, ResilienceReport, ResilienceScenarioResult


class ResilienceAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.engine = ForecastEngine()
        self.analyzer = ResilienceAnalyzer(self.engine)
        self.request_date = date(2026, 4, 1)

    def make_event(
        self,
        event_id: str,
        category: str,
        *,
        direction: str = "debit",
        amount: str = "100",
        day: date | None = None,
        income: bool = False,
    ) -> NormalizedEvent:
        event_day = day or date(2026, 3, 15)
        amt = Decimal(amount)
        return NormalizedEvent(
            event_id=event_id,
            user_id="user_res",
            event_type="income" if income else "expense",
            description=f"Payroll credit" if income else f"Test {category}",
            category=category,
            direction=direction,
            amount=amt,
            currency="USD",
            amount_home_currency=amt,
            conversion_rate=Decimal("1"),
            conversion_rate_date=event_day,
            amount_source="test",
            event_date=event_day,
            settlement_date=event_day,
            status="settled",
            linked_event_id=None,
            flexibility="fixed",
            minimum_allowed_amount=None,
            financial_meaning="income" if income else "expense",
            is_recurring=True,
            is_confirmed_income=income,
            is_confirmed_future_payment=False,
            is_refund=False,
            is_transfer=False,
            included_in_cash_state=True,
            exclusion_reason=None,
            evidence_resolution=None,
        )

    def make_state(self, balance="1000", minimum="200", events=()) -> FinancialState:
        return FinancialState(
            request_id="req_res",
            user_id="user_res",
            request_date=self.request_date,
            home_currency="USD",
            available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            events=tuple(events),
            recurring_expenses=(),
            one_time_expenses=(),
            confirmed_income=tuple(e for e in events if e.is_confirmed_income),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    def test_resilience_report_label_and_structure(self):
        """Verify report is labeled as RESILIENCE ANALYSIS and contains all stress tests."""
        sal1 = self.make_event("sal_1", "salary", amount="1500", day=date(2026, 2, 15), direction="credit", income=True)
        sal2 = self.make_event("sal_2", "salary", amount="1500", day=date(2026, 3, 15), direction="credit", income=True)
        state = self.make_state(balance="1000", minimum="200", events=(sal1, sal2))
        plan_payments = (ProposedPayment(payment_date=self.request_date, amount=Decimal("400")),)

        report = self.analyzer.analyze_plan_resilience(
            state=state,
            plan_payments=plan_payments,
            unexpected_expense_amount=Decimal("150"),
        )

        self.assertEqual(report.label, "RESILIENCE ANALYSIS")
        self.assertTrue(report.is_baseline_safe)
        self.assertEqual(len(report.stress_results), 3)

        names = [r.stress_test_name for r in report.stress_results]
        self.assertIn("SALARY_DELAY_3_DAYS", names)
        self.assertIn("SALARY_DELAY_7_DAYS", names)
        self.assertIn("UNEXPECTED_EXPENSE_150", names)

    def test_salary_delay_stress_test_metrics(self):
        """Verify salary delay correctly reports safe/unsafe, lowest balance, and safety margin."""
        sal1 = self.make_event("sal_1", "salary", amount="1500", day=date(2026, 2, 15), direction="credit", income=True)
        sal2 = self.make_event("sal_2", "salary", amount="1500", day=date(2026, 3, 15), direction="credit", income=True)
        # Rent happens on 16th of each month (200)
        rent1 = self.make_event("rent_1", "rent", amount="200", day=date(2026, 2, 16), direction="debit")
        rent2 = self.make_event("rent_2", "rent", amount="200", day=date(2026, 3, 16), direction="debit")
        # Balance = 350, Min = 200. Purchase = 200 on 2026-04-01 (leaves 150 < 200).
        # Normal salary lands on 2026-04-15 (+1500) -> on Apr 15 balance becomes 1650, Rent on Apr 16 leaves 1450 >= 200.
        # But if salary is delayed by 3 days (to Apr 18), on Apr 16 Rent is charged:
        # Balance drops: 350 - 200 (purchase) - 200 (rent) = -50 < 200 (Unsafe!)
        state = self.make_state(balance="350", minimum="200", events=(sal1, sal2, rent1, rent2))
        plan_payments = (ProposedPayment(payment_date=self.request_date, amount=Decimal("200")),)

        report = self.analyzer.analyze_plan_resilience(
            state=state,
            plan_payments=plan_payments,
        )

        res_delay_3 = [r for r in report.stress_results if r.stress_test_name == "SALARY_DELAY_3_DAYS"][0]
        self.assertFalse(res_delay_3.is_safe)
        self.assertLess(res_delay_3.safety_margin, Decimal("0"))

    def test_unexpected_expense_configurable_amount(self):
        """Verify configurable unexpected emergency expense shock."""
        sal1 = self.make_event("sal_1", "salary", amount="1500", day=date(2026, 2, 15), direction="credit", income=True)
        sal2 = self.make_event("sal_2", "salary", amount="1500", day=date(2026, 3, 15), direction="credit", income=True)
        state = self.make_state(balance="1000", minimum="200", events=(sal1, sal2))
        plan_payments = (ProposedPayment(payment_date=self.request_date, amount=Decimal("400")),)

        # Baseline lowest balance is 600 (margin 400).
        # Inject unexpected expense of 500 -> lowest balance becomes 100 < 200 (margin -100).
        report = self.analyzer.analyze_plan_resilience(
            state=state,
            plan_payments=plan_payments,
            unexpected_expense_amount=Decimal("500"),
        )

        res_shock = [r for r in report.stress_results if r.stress_test_name == "UNEXPECTED_EXPENSE_500"][0]
        self.assertFalse(res_shock.is_safe)
        self.assertEqual(res_shock.lowest_balance, Decimal("100"))
        self.assertEqual(res_shock.safety_margin, Decimal("-100"))


if __name__ == "__main__":
    unittest.main()

