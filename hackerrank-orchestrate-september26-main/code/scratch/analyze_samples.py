import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from data_loader import DataLoader

loader = DataLoader('dataset')
loader.load_all()
profiles = {p.user_id: p for p in loader.load_profiles()}

with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

for s in samples:
    u = s['user_id']
    p = profiles[u]
    print(f"{s['request_id']} ({u}): req_amt={s['requested_amount']}, safe_now={s['amount_safe_to_pay']}, status={s['affordability_status']}, method={s['recommended_payment_method']}, earliest={s['earliest_date_for_full_payment']}, changes={s['spending_changes_needed']}")
    print(f"   Plan: {s['payment_plan']}")
    print(f"   Explanation: {s['decision_explanation']}")
    print()

