import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from data_loader import DataLoader
from financial_state_service import FinancialStateService, NormalizedEvent
from message_interpreter import MessageInterpreter

loader = DataLoader('dataset')
loader.load_all()
messages = loader.load_messages()
interpreter = MessageInterpreter()

user_salary_facts = {}
for m in messages:
    facts = interpreter.interpret(m.__dict__)
    for f in facts:
        if f.amendment_type in ('salary_change', 'salary_delay'):
            user_salary_facts[m.user_id] = f

state_service = FinancialStateService('dataset')

with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

def simulate_90_days(state, user_fact=None, proposed_payments=(), spending_changes=()):
    # spending_changes: map of event_id -> new_amount (or 0 for stop)
    stop_events = set()
    reduce_events = {}
    for sc in spending_changes:
        if sc.startswith('stop:'):
            stop_events.add(sc.split(':')[1])
        elif sc.startswith('reduce_to:'):
            parts = sc.split(':')
            reduce_events[parts[1]] = Decimal(parts[2])

    end_date = state.request_date + timedelta(days=90)
    changes = defaultdict(lambda: Decimal('0'))

    # 1. Apply events in state
    for event in state.events:
        if not event.included_in_cash_state or event.amount_home_currency is None:
            continue
        eff_date = event.settlement_date or event.event_date
        if eff_date < state.request_date or eff_date > end_date:
            continue
        
        # Check spending change
        amt = event.amount_home_currency
        if event.event_id in stop_events:
            continue
        elif event.event_id in reduce_events:
            amt = reduce_events[event.event_id]

        if event.direction == 'debit':
            changes[eff_date] -= amt
        elif event.direction == 'credit' and (event.is_confirmed_income or (event.status == 'settled' and event.financial_meaning in {'refund', 'investment', 'other'})):
            changes[eff_date] += amt

    # 2. Recurring expenses projection
    # Group recurring expenses
    groups = defaultdict(list)
    for event in state.recurring_expenses:
        if event.included_in_cash_state and event.amount_home_currency is not None:
            groups[(event.event_type, event.category, event.currency, event.description)].append(event)

    for events in groups.values():
        ordered = sorted(events, key=lambda e: e.settlement_date or e.event_date)
        dates = [e.settlement_date or e.event_date for e in ordered]
        if len(dates) < 3:
            continue
        intervals = [(r - l).days for l, r in zip(dates, dates[1:]) if (r - l).days > 0]
        if not intervals:
            continue
        interval = int(sorted(intervals)[len(intervals)//2])
        if interval <= 0:
            continue

        actual_horizon_dates = {d for d in dates if state.request_date <= d <= end_date}
        anchors = [d for d in dates if d < state.request_date]
        if not anchors:
            continue
        next_d = max(anchors) + timedelta(days=interval)
        last_event = ordered[-1]
        proj_amt = last_event.amount_home_currency
        if last_event.event_id in stop_events:
            continue
        elif last_event.event_id in reduce_events:
            proj_amt = reduce_events[last_event.event_id]

        while next_d <= end_date:
            if next_d not in actual_horizon_dates and not any(abs((a - next_d).days) <= 7 for a in actual_horizon_dates):
                changes[next_d] -= proj_amt
            next_d += timedelta(days=interval)

    # 3. Recurring salary projection
    # Check if user has recurring salary
    inc_events = [e for e in state.events if e.event_type.lower() == 'income' and e.included_in_cash_state]
    payroll_events = [e for e in inc_events if 'payroll' in e.description.lower() or 'salary' in e.description.lower()]
    is_final_payroll = any('final employer payroll' in e.description.lower() for e in payroll_events)
    
    if payroll_events and not is_final_payroll:
        ordered_inc = sorted(payroll_events, key=lambda e: e.settlement_date or e.event_date)
        last_inc = ordered_inc[-1]
        
        # Determine recurring salary amount & day of month
        salary_amt = last_inc.amount_home_currency
        salary_day = (last_inc.settlement_date or last_inc.event_date).day
        
        # Check message facts
        delayed_date = None
        if user_fact:
            if user_fact.amendment_type == 'salary_change':
                if user_fact.amount is not None:
                    salary_amt = user_fact.amount
            elif user_fact.amendment_type == 'salary_delay':
                if user_fact.date is not None:
                    delayed_date = user_fact.date
                if user_fact.amount is not None:
                    salary_amt = user_fact.amount

        # Actual scheduled income in horizon
        actual_inc_dates = {e.settlement_date or e.event_date for e in inc_events if state.request_date <= (e.settlement_date or e.event_date) <= end_date and (e.is_confirmed_income or e.status == 'scheduled')}
        
        # Generate monthly dates from request_date to end_date
        # Check from current month to 3 months ahead
        cur_year = state.request_date.year
        cur_month = state.request_date.month
        for m_offset in range(4):
            m = cur_month + m_offset
            y = cur_year + (m - 1) // 12
            m = (m - 1) % 12 + 1
            try:
                pay_d = date(y, m, salary_day)
            except ValueError:
                # Handle month day overflow if any
                pay_d = date(y, m, 28)
            
            if m_offset == 0 and delayed_date and delayed_date >= state.request_date:
                pay_d = delayed_date
                
            if state.request_date <= pay_d <= end_date:
                if pay_d not in actual_inc_dates and not any(abs((a - pay_d).days) <= 7 for a in actual_inc_dates):
                    changes[pay_d] += salary_amt

    # 4. Proposed payments
    for p_date, p_amt in proposed_payments:
        if state.request_date <= p_date <= end_date:
            changes[p_date] -= p_amt

    # 5. Daily balance trajectory
    daily = {}
    bal = state.available_balance
    cur = state.request_date
    lowest = None
    lowest_d = None
    while cur <= end_date:
        bal += changes[cur]
        daily[cur] = bal
        if lowest is None or bal < lowest:
            lowest = bal
            lowest_d = cur
        cur += timedelta(days=1)

    margin = lowest - state.minimum_balance_to_keep
    return daily, lowest, lowest_d, margin

for s in samples:
    req_id = s['request_id']
    u = s['user_id']
    state = state_service.reconstruct(req_id)
    fact = user_salary_facts.get(u)
    
    # Safe now
    daily, lowest, lowest_d, margin = simulate_90_days(state, fact)
    safe_now = max(Decimal('0'), min(Decimal(s['requested_amount']), margin))
    exp_safe_now = Decimal(s['amount_safe_to_pay'])
    
    # Earliest date
    req_amt = Decimal(s['requested_amount'])
    earliest = None
    for day_idx in range(91):
        cand_d = state.request_date + timedelta(days=day_idx)
        _, _, _, cand_margin = simulate_90_days(state, fact, proposed_payments=[(cand_d, req_amt)])
        if cand_margin >= Decimal('0'):
            earliest = cand_d
            break
            
    exp_earliest = s['earliest_date_for_full_payment'] or None
    
    diff_safe = 'MATCH' if safe_now == exp_safe_now else f'DIFF (calc={safe_now}, exp={exp_safe_now})'
    diff_date = 'MATCH' if str(earliest or '') == str(exp_earliest or '') else f'DIFF (calc={earliest}, exp={exp_earliest})'
    print(f"{req_id} ({u}): safe_now={diff_safe} | earliest={diff_date}")

