import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from financial_state_service import FinancialStateService
from datetime import date, timedelta
from decimal import Decimal

state_service = FinancialStateService('dataset')
state = state_service.reconstruct('request_05')

print('User 05 request date:', state.request_date)
print('User 05 available balance:', state.available_balance)
print('User 05 min balance:', state.minimum_balance_to_keep)

# Check all events from request_date onwards
print('\n--- Events on or after request_date ---')
for e in state.events:
    d = e.settlement_date or e.event_date
    if d >= state.request_date:
        print(f"{e.event_id} | {d} | {e.event_type} | {e.direction} | {e.amount_home_currency} | {e.status} | inc={e.included_in_cash_state} | {e.description}")

# Check recurring events before request_date
print('\n--- Recurring expenses ---')
for e in state.recurring_expenses:
    d = e.settlement_date or e.event_date
    print(f"{e.event_id} | {d} | {e.amount_home_currency} | {e.description}")

