import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_loader import DataLoader
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, median
import csv

loader = DataLoader('dataset')
loader.load_all()

# For user_02:
# Target safe_now = 17229139.20
# Target min_keep = 29158400
# Target lowest_bal = 17229139.20 + 29158400 = 46387539.20
# Available bal = 60383889.20
# Drop in balance before lowest point = 60383889.20 - 46387539.20 = 13996350.00 exactly!

print("Target drop in balance = 13,996,350.00")

# What expenses happen between 2025-08-05 and 2025-08-15 (lowest point date)?
# Let's inspect the fixed amounts:
# Aug 7: Utilities -> ?
# Aug 8: Pending merchant debit (event_185) -> 1,651,100
# Aug 8: Insurance -> 1,132,400 (fixed)
# Aug 9: Education -> 3,040,000 (fixed)
# Aug 9: Groceries -> (10 days from July 30 = Aug 9) -> ?
# Aug 11: Healthcare -> ?
# Aug 12: Transport -> (14 days from July 29 = Aug 12) -> ?
# Aug 13: Cloud storage -> 369,550 (fixed)
# Aug 15: Entertainment -> ?

# Sum of fixed knowns: 1651100 + 1132400 + 3040000 + 369550 = 6,193,050
# Remaining to drop = 13996350 - 6193050 = 7,803,300.00

# What are the other expenses?
# Utilities (Aug 7)
# Groceries (Aug 9)
# Healthcare (Aug 11)
# Transport (Aug 12)
# Let's see their last amounts vs mean amounts:
# Utilities: last=2141849.94, mean=2008873.35, median=2081730.85
# Healthcare: last=1538498.10, mean=1527011.96, median=1538498.10
# Groceries: last=1913686.86, mean=1928424.38
# Transport: last=1062310.27, mean=1236166.75

# Let's test combinations:
# If mean: 2008873.35 + 1527011.96 + 1928424.38 + 1236166.75 = 6,700,476.44 (missing 1.1M dining?)
# Dining next date: July 30 + 21 days = Aug 20 (after Aug 15).

