import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from data_loader import DataLoader
from financial_state_service import FinancialStateService, NormalizedEvent
from message_interpreter import MessageInterpreter, MessageFact
import csv

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

def add_months(d: date, num_months: int, target_day: int) -> date:
    m = d.month + num_months
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    # Day clamping
    max_days = [0, 31, 29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    day = min(target_day, max_days[m])
    return date(y, m, day)

def simulate_calendar(state, user_fact=None, proposed_payments=(), spending_changes=()):
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

    # 1. Any confirmed scheduled events strictly in the future (between request_date and end_date)
    for event in state.events:
        if not event.included_in_cash_state or event.amount_home_currency is None:
            continue
        eff_date = event.settlement_date or event.event_date
        if eff_date < state.request_date or eff_date > end_date:
            continue
        
        amt = event.amount_home_currency
        if event.event_id in stop_events:
            continue
        elif event.event_id in reduce_events:
            amt = reduce_events[event.event_id]

        if event.direction == 'debit':
            changes[eff_date] -= amt
        elif event.direction == 'credit' and (event.is_confirmed_income or (event.status == 'settled' and event.financial_meaning in {'refund', 'investment', 'other'})):
            changes[eff_date] += amt

    # 2. Historical debits projection
    past_debits = [
        e for e in state.events 
        if e.included_in_cash_state and e.direction == 'debit' and (e.settlement_date or e.event_date) < state.request_date
    ]
    group_map = defaultdict(list)
    for e in past_debits:
        key = (e.category, e.description) if e.category in ('subscription', 'rent', 'debt_repayment', 'education', 'utilities', 'family_support') else (e.category, '')
        group_map[key].append(e)

    for (cat, desc), evts in group_map.items():
        ordered = sorted(evts, key=lambda x: x.settlement_date or x.event_date)
        if len(ordered) < 2:
            continue
        dates = [x.settlement_date or x.event_date for x in ordered]
        intervals = [(r - l).days for l, r in zip(dates, dates[1:]) if (r - l).days > 0]
        if not intervals:
            continue
        interval = int(median(intervals))
        if interval <= 0:
            continue

        last_evt = ordered[-1]
        last_date = dates[-1]
        base_amt = last_evt.amount_home_currency
        assert base_amt is not None

        stream_event_ids = {x.event_id for x in ordered}
        if any(eid in stop_events for eid in stream_event_ids):
            continue
        for eid in stream_event_ids:
            if eid in reduce_events:
                base_amt = reduce_events[eid]

        # Monthly cadence vs day-offset cadence
        is_monthly = 27 <= interval <= 32
        target_dom = last_date.day

        if is_monthly:
            for m_offset in range(1, 5):
                proj_d = add_months(last_date, m_offset, target_dom)
                if state.request_date <= proj_d <= end_date:
                    changes[proj_d] -= base_amt
        else:
            next_d = last_date + timedelta(days=interval)
            while next_d <= end_date:
                if next_d >= state.request_date:
                    changes[next_d] -= base_amt
                next_d += timedelta(days=interval)

    # 3. Recurring income projection
    past_credits = [
        e for e in state.events
        if e.included_in_cash_state and (e.direction == 'credit' or e.event_type.lower() == 'income') and (e.settlement_date or e.event_date) < state.request_date
    ]
    is_final = any('final employer payroll' in e.description.lower() for e in state.events)
    if not is_final and past_credits:
        # Check standard monthly salary
        payroll_events = [e for e in past_credits if e.category == 'salary' or e.event_type.lower() == 'income']
        if payroll_events:
            ordered_inc = sorted(payroll_events, key=lambda e: e.settlement_date or e.event_date)
            last_inc = ordered_inc[-1]
            salary_amt = last_inc.amount_home_currency
            salary_dom = (last_inc.settlement_date or last_inc.event_date).day
            
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

            actual_future_inc_dates = {
                e.settlement_date or e.event_date for e in state.events
                if state.request_date <= (e.settlement_date or e.event_date) <= end_date and (e.is_confirmed_income or e.status == 'scheduled')
            }

            if salary_amt is not None:
                for m_offset in range(0, 5):
                    proj_d = add_months(state.request_date, m_offset, salary_dom)
                    if m_offset == 0 and delayed_date and delayed_date >= state.request_date:
                        proj_d = delayed_date
                    if state.request_date <= proj_d <= end_date:
                        if proj_d not in actual_future_inc_dates and not any(abs((a - proj_d).days) <= 7 for a in actual_future_inc_dates):
                            changes[proj_d] += salary_amt

    # 4. Proposed payments
    for p_date, p_amt in proposed_payments:
        if state.request_date <= p_date <= end_date:
            changes[p_date] -= p_amt

    # 5. Balance
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

print("Testing samples with calendar-aligned projection:")
match_safe = 0
match_earliest = 0
for s in samples:
    req_id = s['request_id']
    u = s['user_id']
    state = state_service.reconstruct(req_id)
    fact = user_salary_facts.get(u)
    
    # Safe now
    daily, lowest, lowest_d, margin = simulate_calendar(state, fact)
    safe_now = max(Decimal('0'), min(Decimal(s['requested_amount']), margin))
    exp_safe_now = Decimal(s['amount_safe_to_pay'])
    
    # Earliest date
    req_amt = Decimal(s['requested_amount'])
    earliest = None
    for day_idx in range(91):
        cand_d = state.request_date + timedelta(days=day_idx)
        _, _, _, cand_margin = simulate_calendar(state, fact, proposed_payments=[(cand_d, req_amt)])
        if cand_margin >= Decimal('0'):
            earliest = cand_d
            break
            
    exp_earliest = s['earliest_date_for_full_payment'] or None
    
    diff_safe = 'MATCH' if safe_now == exp_safe_now else f'DIFF (calc={safe_now}, exp={exp_safe_now})'
    diff_date = 'MATCH' if str(earliest or '') == str(exp_earliest or '') else f'DIFF (calc={earliest}, exp={exp_earliest})'
    if safe_now == exp_safe_now: match_safe += 1
    if str(earliest or '') == str(exp_earliest or ''): match_earliest += 1
    print(f"{req_id} ({u}): safe_now={diff_safe:<35} | earliest={diff_date}")

print(f"\nSafe now match: {match_safe}/{len(samples)}, Earliest date match: {match_earliest}/{len(samples)}")

