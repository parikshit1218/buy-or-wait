import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from financial_state_service import FinancialStateService
from decimal import Decimal

loader = DataLoader('dataset')
loader.load_all()
events = loader.load_events()

u5_events = [e for e in events if e.user_id == 'user_05']
print(f"Total u5 events: {len(u5_events)}")
for e in u5_events:
    print(f"{e.event_id} | {e.event_date} | {e.settlement_date} | {e.event_type} | {e.direction} | {e.category} | {e.amount} | {e.status} | {e.description}")

