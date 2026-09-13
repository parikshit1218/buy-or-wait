import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
import csv

loader = DataLoader('dataset')
loader.load_all()
options = loader.load_payment_options()

with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

for s in samples:
    req_id = s['request_id']
    opts = [o for o in options if o.request_id == req_id]
    print(f"=== {req_id} ({s['request_type']}, amt={s['requested_amount']}) ===")
    print(f"  Chosen method: {s['recommended_payment_method']} | Plan: {s['payment_plan']}")
    for o in opts:
        print(f"    opt={o.payment_option_id} | installments={o.installment_count} | start={o.start_date} | interval={o.interval_days} | total={o.total_payable_amount} | fee={o.explicit_financing_fee}")

