import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from decision_agent import DecisionAgent
from data_loader import DataLoader
from models import FinancialRequest
from datetime import date
from decimal import Decimal

agent = DecisionAgent('dataset')

with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

print(f"Evaluating {len(samples)} sample requests with DecisionAgent...\n")

correct_status = 0
correct_method = 0
correct_plan = 0
correct_changes = 0

for s in samples:
    req = FinancialRequest(
        request_id=s['request_id'],
        user_id=s['user_id'],
        request_date=date.fromisoformat(s['request_date']),
        request_type=s['request_type'],
        requested_amount=Decimal(s['requested_amount']),
        desired_completion_date=date.fromisoformat(s['desired_completion_date']),
        allows_partial_payment=s['allows_partial_payment'].strip().lower() == 'true',
        request_text=s['request_text'],
    )
    
    out = agent.evaluate_request(req)
    
    st_match = out.affordability_status == s['affordability_status']
    m_match = out.recommended_payment_method == s['recommended_payment_method']
    p_match = out.payment_plan == s['payment_plan']
    ch_match = out.spending_changes_needed == s['spending_changes_needed']
    
    if st_match: correct_status += 1
    if m_match: correct_method += 1
    if p_match: correct_plan += 1
    if ch_match: correct_changes += 1
    
    print(f"[{s['request_id']}]")
    print(f"  Status: calc={out.affordability_status:<20} | exp={s['affordability_status']:<20} | {'MATCH' if st_match else 'FAIL'}")
    print(f"  Method: calc={out.recommended_payment_method:<20} | exp={s['recommended_payment_method']:<20} | {'MATCH' if m_match else 'FAIL'}")
    print(f"  Plan:   calc={out.payment_plan}")
    print(f"          exp ={s['payment_plan']}")
    print(f"  Changes:calc={out.spending_changes_needed:<20} | exp={s['spending_changes_needed']:<20} | {'MATCH' if ch_match else 'FAIL'}")
    print(f"  Earliest:calc={out.earliest_date_for_full_payment} | exp={s['earliest_date_for_full_payment']}")
    print(f"  Expl: {out.decision_explanation}")
    print()

print("="*60)
print(f"Sample Accuracy Breakdown (out of {len(samples)}):")
print(f"  Affordability Status: {correct_status}/{len(samples)} ({correct_status/len(samples)*100:.1f}%)")
print(f"  Recommended Method:   {correct_method}/{len(samples)} ({correct_method/len(samples)*100:.1f}%)")
print(f"  Payment Plan:         {correct_plan}/{len(samples)} ({correct_plan/len(samples)*100:.1f}%)")
print(f"  Spending Changes:     {correct_changes}/{len(samples)} ({correct_changes/len(samples)*100:.1f}%)")
print("="*60)

