import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from data_loader import DataLoader
from financial_state_service import FinancialStateService
from message_interpreter import MessageInterpreter
from models import PaymentOption

loader = DataLoader('dataset')
loader.load_all()
profiles = {p.user_id: p for p in loader.load_profiles()}
messages = loader.load_messages()
payment_options = loader.load_payment_options()
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

# Let's test full candidate generation & ranking for all 25 samples
print("Starting full engine test on 25 samples...")

