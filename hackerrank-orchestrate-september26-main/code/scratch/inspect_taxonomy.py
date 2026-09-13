import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from collections import Counter, defaultdict

loader = DataLoader('dataset')
loader.load_all()
events = loader.load_events()

# Inspect categories and event_types
cat_counter = Counter(e.category for e in events)
type_counter = Counter(e.event_type for e in events)
print("Categories:", cat_counter)
print("Event types:", type_counter)

# Check user_01 events across time
u1_events = [e for e in events if e.user_id == 'user_01']
print(f"\nUser 01 total events: {len(u1_events)}")
for e in u1_events:
    print(f"  {e.event_id} | {e.event_date} | {e.event_type} | {e.category} | {e.direction} | {e.amount} | {e.flexibility} | {e.description}")

