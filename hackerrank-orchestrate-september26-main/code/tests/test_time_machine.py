"""Unit tests for the optional Financial Time Machine scenario simulator."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from financial_state_service import FinancialState
from forecast_engine import ForecastEngine
from models import FinancialProfile, FinancialRequest, PaymentOption
from time_machine import FinancialTimeMachine, ScenarioResult


class FinancialTimeMachineTests(unittest.TestCase):
    def setUp(self):
        self.engine = ForecastEngine()
        self.time_machine = FinancialTimeMachine(self.engine)
        self.request_date = date(2026, 4, 1)
        self.deadline = date(2026, 5, 1)

    def make_profile(self, balance="1000", minimum="200") -> FinancialProfile:
        return FinancialProfile(
            user_id="user_tm",
            home_currency="USD",
            current_available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            financial_priorities=("emergency_savings",),
            expense_categories_to_protect=(),
            expense_categories_user_is_willing_to_reduce=(),
            expense_categories_user_is_willing_to_stop=(),
            payment_methods_user_will_consider=("full_payment", "partial_payment", "installments"),
            max_installment_months=6,
        )

    def make_request(self, amount="500") -> FinancialRequest:
        return FinancialRequest(
            request_id="req_tm",
            user_id="user_tm",
            request_date=self.request_date,
            request_type="purchase",
            requested_amount=Decimal(amount),
            desired_completion_date=self.deadline,
            allows_partial_payment=True,
            request_text="Time machine test",
        )

    def make_state(self, balance="1000", minimum="200") -> FinancialState:
        return FinancialState(
            request_id="req_tm",
            user_id="user_tm",
            request_date=self.request_date,
            home_currency="USD",
            available_balance=Decimal(balance),
            minimum_balance_to_keep=Decimal(minimum),
            events=(),
            recurring_expenses=(),
            one_time_expenses=(),
            confirmed_income=(),
            confirmed_future_payments=(),
            refunds=(),
            transfers=(),
        )

    def test_buy_now_scenario(self):
        req = self.make_request(amount="400")
        state = self.make_state(balance="1000", minimum="200")

        res = self.time_machine.simulate_buy_now(req, state)
        self.assertEqual(res.scenario_name, "BUY_NOW")
        self.assertTrue(res.is_safe)
        self.assertEqual(res.lowest_balance, Decimal("600"))  # 1000 - 400 = 600
        self.assertEqual(res.lowest_balance_date, self.request_date)
        self.assertEqual(res.safety_margin, Decimal("400"))  # 600 - 200 = 400
        self.assertEqual(res.completion_date, self.request_date)
        self.assertEqual(res.total_amount_paid, Decimal("400"))
        self.assertEqual(res.number_of_payments, 1)

    def test_wait_scenario(self):
        req = self.make_request(amount="400")
        state = self.make_state(balance="1000", minimum="200")
        future_date = self.request_date + timedelta(days=20)

        res = self.time_machine.simulate_wait(req, state, wait_date=future_date)
        self.assertEqual(res.scenario_name, "WAIT")
        self.assertTrue(res.is_safe)
        self.assertEqual(res.completion_date, future_date)
        self.assertEqual(res.total_amount_paid, Decimal("400"))
        self.assertEqual(res.number_of_payments, 1)

    def test_partial_payment_scenario(self):
        req = self.make_request(amount="500")
        state = self.make_state(balance="500", minimum="200")  # safe_now = 300
        future_date = self.request_date + timedelta(days=15)

        res = self.time_machine.simulate_partial_payment(
            req, state, amount_safe_to_pay=Decimal("300"), second_payment_date=future_date
        )
        self.assertEqual(res.scenario_name, "PARTIAL_PAYMENT")
        self.assertEqual(res.number_of_payments, 2)
        self.assertEqual(res.total_amount_paid, Decimal("500"))
        self.assertEqual(res.completion_date, future_date)
        p1, p2 = res.payments
        self.assertEqual(p1.amount, Decimal("300"))
        self.assertEqual(p2.amount, Decimal("200"))

    def test_installment_option_scenario(self):
        opt = PaymentOption(
            payment_option_id="opt_tm_3m",
            request_id="req_tm",
            payment_method="installments",
            payment_amount=Decimal("170"),
            number_of_payments=3,
            first_payment_date=self.request_date,
            payment_frequency_days=30,
            financing_fee=Decimal("10"),
            total_payable_amount=Decimal("510"),
        )
        state = self.make_state(balance="1000", minimum="200")

        res = self.time_machine.simulate_installment_option(opt, state)
        self.assertEqual(res.scenario_name, "INSTALLMENTS_opt_tm_3m")
        self.assertEqual(res.number_of_payments, 3)
        self.assertEqual(res.total_amount_paid, Decimal("510"))
        self.assertEqual(res.completion_date, self.request_date + timedelta(days=60))

    def test_simulate_all_scenarios_returns_complete_suite(self):
        req = self.make_request(amount="500")
        prof = self.make_profile(balance="1000", minimum="200")
        state = self.make_state(balance="1000", minimum="200")
        opt = PaymentOption(
            payment_option_id="opt_tm_1",
            request_id="req_tm",
            payment_method="installments",
            payment_amount=Decimal("170"),
            number_of_payments=3,
            first_payment_date=self.request_date,
            payment_frequency_days=30,
            financing_fee=Decimal("10"),
            total_payable_amount=Decimal("510"),
        )

        scenarios = self.time_machine.simulate_all_scenarios(
            request=req,
            profile=prof,
            state=state,
            payment_options=(opt,),
        )

        names = [s.scenario_name for s in scenarios]
        self.assertIn("BUY_NOW", names)
        self.assertIn("WAIT", names)
        self.assertIn("PARTIAL_PAYMENT", names)
        self.assertIn("INSTALLMENTS_opt_tm_1", names)

        for s in scenarios:
            self.assertIsInstance(s.is_safe, bool)
            self.assertIsInstance(s.lowest_balance, Decimal)
            self.assertIsInstance(s.lowest_balance_date, date)
            self.assertIsInstance(s.safety_margin, Decimal)
            self.assertIsInstance(s.total_amount_paid, Decimal)
            self.assertIsInstance(s.number_of_payments, int)


if __name__ == "__main__":
    unittest.main()

