import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from datetime import date, timedelta
from decimal import Decimal

loader = DataLoader('dataset')
loader.load_all()
events = [e for e in loader.load_events() if e.user_id == 'user_02']

# User 02 request date: 2025-08-05
# Let's inspect each stream and how each past event recurs
print("User 02 recurring streams:")
# Find each stream
streams = {}
for e in events:
    if e.direction == 'debit' and (e.settlement_date or e.event_date) < date(2025, 8, 5):
        key = (e.category, e.description)
        if key not in streams:
            streams[key] = []
        streams[key].append(e)

for key, evts in sorted(streams.items()):
    ordered = sorted(evts, key=lambda x: x.settlement_date or x.event_date)
    dates = [x.settlement_date or x.event_date for x in ordered]
    amounts = [x.amount for x in ordered]
    print(f"{key}: {len(evts)} occurrences | last_date={dates[-1]} | last_amt={amounts[-1]} | amounts={amounts[-3:]}")

