import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from data_loader import DataLoader
from financial_state_service import FinancialStateService
from message_interpreter import MessageInterpreter

loader = DataLoader('dataset')
loader.load_all()
profiles = {p.user_id: p for p in loader.load_profiles()}
messages = loader.load_messages()
interpreter = MessageInterpreter()

# Map user messages
user_salary_facts = {}
for m in messages:
    facts = interpreter.interpret(m.__dict__)
    for f in facts:
        if f.amendment_type in ('salary_change', 'salary_delay'):
            user_salary_facts[m.user_id] = f

state_service = FinancialStateService('dataset')

with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

for s in samples:
    u = s['user_id']
    req_id = s['request_id']
    req_date = date.fromisoformat(s['request_date'])
    state = state_service.reconstruct(req_id)
    
    # Check income history for user
    inc_events = [e for e in state.events if e.event_type.lower() == 'income' and e.included_in_cash_state]
    payroll_events = [e for e in inc_events if 'payroll' in e.description.lower() or 'salary' in e.description.lower()]
    
    fact = user_salary_facts.get(u)
    print(f"{req_id} ({u}): avail={state.available_balance}, min_keep={state.minimum_balance_to_keep}")
    print(f"  Salary fact from message: {fact}")
    print(f"  Historical payroll events ({len(payroll_events)}):")
    for pe in payroll_events[-3:]:
        print(f"     {pe.event_id} | {pe.event_date} | {pe.amount_home_currency} | {pe.description} | status={pe.status}")

