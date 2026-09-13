import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from financial_state_service import FinancialStateService
from message_interpreter import MessageInterpreter
from datetime import date
from decimal import Decimal

state_service = FinancialStateService('dataset')
loader = DataLoader('dataset')
loader.load_all()

for uid, req_id in [('user_09', 'request_09'), ('user_11', 'request_11'), ('user_13', 'request_13'), ('user_17', 'request_17'), ('user_19', 'request_19'), ('user_21', 'request_21'), ('user_22', 'request_22')]:
    state = state_service.reconstruct(req_id)
    print(f"=== {req_id} ({uid}) ===")
    print(f"  Avail bal: {state.available_balance}, Min keep: {state.minimum_balance_to_keep}")
    # Print recurring debits grouped
    debits = [e for e in state.events if e.included_in_cash_state and e.direction == 'debit']
    print(f"  Total debits: {len(debits)}")
    # Print upcoming events after request_date
    future_events = [e for e in state.events if (e.settlement_date or e.event_date) >= state.request_date]
    print(f"  Future events in state: {len(future_events)}")
    for fe in future_events:
        print(f"     {fe.event_id} | {fe.event_date} | {fe.settlement_date} | {fe.direction} | {fe.amount_home_currency} | {fe.status} | {fe.description}")

