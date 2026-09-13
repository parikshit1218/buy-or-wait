import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from decimal import Decimal
import csv

loader = DataLoader('dataset')
loader.load_all()

# Get sample row 2 (request_02)
with open('dataset/sample_requests.csv', encoding='utf-8') as f:
    samples = list(csv.DictReader(f))

s2 = samples[1]
print("Sample 2:", s2)

profiles = {p.user_id: p for p in loader.load_profiles()}
p2 = profiles['user_02']
print("User 02 profile:", p2)

# List all user 02 events
events = [e for e in loader.load_events() if e.user_id == 'user_02']
for e in sorted(events, key=lambda x: x.event_date):
    print(f"{e.event_id} | {e.event_date} | {e.settlement_date} | {e.event_type} | {e.direction} | {e.category} | {e.amount} {e.currency} | {e.status} | {e.description}")

