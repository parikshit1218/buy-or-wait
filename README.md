# "Buy or Wait?" — Autonomous Financial Decision Agent

**HackerRank Orchestrate (September 2026)**  
Deterministic, zero-hallucination multi-currency cash flow simulation, risk-aware payment scheduling, and scenario modeling engine.

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Architecture Overview](#2-architecture-overview)
3. [Dataset & Relational Schema](#3-dataset--relational-schema)
4. [Financial-State Reconstruction & Conflict Precedence](#4-financial-state-reconstruction--conflict-precedence)
5. [Image & Message Evidence Processing](#5-image--message-evidence-processing)
6. [90-Day Cash Flow Forecast Engine](#6-90-day-cash-flow-forecast-engine)
7. [Payment Plan Generation & Multi-Criteria Ranking](#7-payment-plan-generation--multi-criteria-ranking)
8. [Spending-Change Optimizer](#8-spending-change-optimizer)
9. [Validation & Decision Explanation Grounding](#9-validation--decision-explanation-grounding)
10. [Financial Time Machine & Resilience Analysis](#10-financial-time-machine--resilience-analysis)
11. [Setup & Installation](#11-setup--installation)
12. [Running Locally](#12-running-locally)
13. [Running Test Suite](#13-running-test-suite)
14. [Generating `output.csv`](#14-generating-outputcsv)
15. [Generating `usage_report.md`](#15-generating-usagereportmd)
16. [Environment Variables](#16-environment-variables)
17. [Known Limitations](#17-known-limitations)

---

## 1. Problem Statement

Given prospective financial purchase requests in `dataset/requests.csv`, determine whether a user can safely afford an expense on their `request_date` or within their `desired_completion_date`.

A recommendation is **SAFE** if and only if the simulated daily balance satisfies:

$$\text{balance}(t) \ge \text{minimum\_balance\_to\_keep} \quad \forall t \in [\text{request\_date}, \text{request\_date} + 90\text{ days}]$$

The agent must output exact predictions for all 250 test requests in `output.csv` adhering to the required 8-column schema:
`request_id`, `amount_safe_to_pay`, `affordability_status`, `recommended_payment_method`, `payment_plan`, `earliest_date_for_full_payment`, `spending_changes_needed`, and `decision_explanation`.

---

## 2. Architecture Overview

The system is built on a modular, decoupled, pipeline architecture that guarantees $100\%$ reproducible, deterministic results without reliance on generative LLMs for numerical arithmetic.

```
                  ┌─────────────────────────────────┐
                  │          Raw Datasets           │
                  │   CSVs, Evidence Images, FX     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │       DataLoader & Indexer      │
                  │  currency.py, data_loader.py    │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │   Financial State Reconstruction│
                  │ financial_state_service.py      │
                  │ (Conflict resolution, FX, imgs) │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │    90-Day Forecast Engine       │
                  │       forecast_engine.py        │
                  │  (Calendar alignment, salaries) │
                  └────────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ Safe-Now Engine  │     │ Earliest-Full Svc │     │ Spending Optimizer│
│safe_now_calc.py  │     │earliest_full...py │     │spending_change.py │
└────────┬─────────┘     └─────────┬─────────┘     └─────────┬─────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │     Candidate Plan Engine       │
                  │   candidate_plan_service.py     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │   Multi-Criteria Plan Ranker    │
                  │        plan_ranker.py           │
                  │   (Strict 6-Tier Hierarchy)     │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │  Decision Explanation Generator │
                  │ decision_explanation_service.py │
                  └────────────────┬────────────────┘
                                   │
                                   ▼
                  ┌─────────────────────────────────┐
                  │ Final Output & Validation Suite │
                  │  output.csv & usage_report.md   │
                  └─────────────────────────────────┘
```

---

## 3. Dataset & Relational Schema

The solution processes the following tables in `dataset/`:
- **`financial_profiles.csv`** (275 users): User home currencies (INR, ZAR, IDR, USD, EUR), opening cash balance, minimum balance reserve threshold, protected vs. flexible expense categories, and accepted payment preferences.
- **`financial_events.csv`** (25,342 records): Historical debits/credits, recurring subscriptions, scheduled salary credits, and pending payments.
- **`requests.csv`** (250 requests): Prospective expense requests requiring evaluation.
- **`sample_requests.csv`** (25 ground-truth examples): Reference benchmarks for tuning and regression assertions.
- **`request_payment_options.csv`** (500 records): Structured installment and financing offers.
- **`exchange_rates.csv`** (134 dated records): Exact offline foreign exchange conversion rates.
- **`messages.csv`** (1,234 messages): Unstructured evidence messages (disputes, cancellations, pay raises, delayed bonuses).
- **`images.csv` & `media/images/`** (16 PNG images): Receipt and payroll document images resolving blank transaction amounts.

---

## 4. Financial-State Reconstruction & Conflict Precedence

Implemented in `code/financial_state_service.py`.

### 4-Tier Conflict Resolution Engine
When transactions duplicate or clash (e.g., initial charge vs. dispute vs. reversal, or duplicate ledger entries), precedence is resolved deterministically:
1. **Explicit Fact Evidence**: Contextual amendments or cancellations proven by parsed messages/images take priority.
2. **Temporal Recency**: Newer transaction records supersede older provisional records.
3. **Settlement State**: `settled` transactions take precedence over unconfirmed `pending` / `scheduled` entries.
4. **Conservative Safety**: In ambiguous ties, the conservative financial interpretation is chosen (higher expense amount or lower income).

All foreign currency transactions are converted into the user's `home_currency` at the exact rate on the transaction settlement date using `code/currency_conversion_service.py`.

---

## 5. Image & Message Evidence Processing

### Multimodal Receipt Image Resolution
- Located in `code/missing_amount_resolver.py`.
- 16 transactions in `financial_events.csv` have blank `amount` fields linked to PNG receipts in `dataset/media/images/`.
- Resolved deterministically using image metadata and bounding-box OCR extraction to inject verified amounts without hallucination.

### Rule-Based Message Interpreter
- Located in `code/message_interpreter.py`.
- Parses natural language messages into structured `MessageFact` objects:
  - **Salary Amendments**: Identifies base salary increases/decreases, pay-date shifts, and confirmed annual bonuses.
  - **Cancellations & Reversals**: Detects subscription terminations and disputed charges to exclude canceled debits.
  - **Transfers**: Distinguishes internal account reallocations from external expenses.

---

## 6. 90-Day Cash Flow Forecast Engine

Implemented in `code/forecast_engine.py`.

### Daily Balance Simulation
For every day $t \in [\text{request\_date}, \text{request\_date} + 90]$:
1. Apply confirmed forward income and salary streams.
2. Apply confirmed future payments and valid non-canceled one-time debits.
3. Apply active recurring expenses aligned by **calendar day-of-month** (preventing 1-day drift in 31-day months).
4. Apply multi-stream salary inflows (supporting semi-monthly and secondary household earners).
5. Apply proposed request payment deductions.
6. Verify end-of-day balance $\text{balance}(t) \ge \text{minimum\_balance\_to\_keep}$.

---

## 7. Payment Plan Generation & Multi-Criteria Ranking

### Candidate Methods Evaluated
- **`full_payment`**: Entire amount paid on `request_date`.
- **`partial_payment`**: Maximum safe amount paid on `request_date`, remaining balance paid on `earliest_date_for_full_payment`.
- **`installments`**: Structured payments using vendor offers from `request_payment_options.csv`.
- **`wait`**: Full payment deferred to `earliest_date_for_full_payment`.
- **`not_recommended`**: Request cannot be safely fulfilled within 90 days or by `desired_completion_date`.

### Strict 6-Tier Ranking Hierarchy (`code/plan_ranker.py`)
1. **Completion Deadline**: Must complete on or before `desired_completion_date`.
2. **Spending Changes**: Plans requiring zero spending changes strictly outrank plans requiring changes.
3. **Total Cost to User**: Minimize total amount paid (including interest/financing fees).
4. **Earliest Start Date**: Prefer plans starting sooner.
5. **Fewer Payments**: Prefer fewer transactions (single payment > partial > installments).
6. **Payment Option ID**: Lower alphanumeric `payment_option_id` breaks remaining ties.

---

## 8. Spending-Change Optimizer

Implemented in `code/spending_change_service.py`.

When no candidate plan is initially safe, the optimizer searches for the smallest effective set of spending modifications:
- **Constraints**: Maximum 3 changes.
- **Scope**: Targets only flexible recurring expenses (`is_flexible=True` and category not in user's `expense_categories_to_protect`).
- **Actions**:
  - `stop:<event_id>`: Cancel subscription/service.
  - `reduce_to:<event_id>:<amount>`: Lower recurring debit to allowed floor (`minimum_allowed_amount`).
- **Non-Interference**: Never targets non-flexible expenses or protected categories.

---

## 9. Validation & Decision Explanation Grounding

- **Automated Validation**: `code/validators.py` and `code/scratch/verify_all_checklist.py` enforce all 20 schema, boundary, and mathematical invariants.
- **Fact-Grounded Explanations**: `code/decision_explanation_service.py` synthesizes concise natural-language rationales citing exact verified numbers (current balance, minimum reserve, fee breakdown, completion date, and specific spending cuts) without mutating decisions.

---

## 10. Financial Time Machine & Resilience Analysis

### Financial Time Machine (`code/time_machine.py`)
Provides interactive scenario analysis across all candidate payment strategies (`BUY_NOW`, `WAIT`, `PARTIAL_PAYMENT`, `INSTALLMENTS_<id>`) returning lowest balance, safety margin, completion date, and total paid.

```bash
python code/main.py --time-machine request_01
```

### Resilience Analysis Layer (`code/resilience_analysis.py`)
Diagnostic stress-testing engine that simulates:
1. Salary delayed by 3 calendar days.
2. Salary delayed by 7 calendar days.
3. Immediate unexpected emergency expense of configurable amount.

```bash
python code/main.py --resilience-analysis request_01 --unexpected-expense 5000
```
*(Note: Analysis tools are diagnostic only and never alter the official `output.csv` decisions).*

---

## 11. Setup & Installation

### Requirements
- **Python**: 3.10+ (tested on Python 3.14)
- **Standard Library**: `decimal`, `datetime`, `pathlib`, `csv`, `collections`, `typing`
- **Testing**: `pytest >= 8.0.0`

### Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/interviewstreet/hackerrank-orchestrate-september26.git
cd hackerrank-orchestrate-september26/hackerrank-orchestrate-september26-main
pip install pytest
```

---

## 12. Running Locally

### Main CLI Interface
```bash
# Display help and CLI options
python code/main.py --help

# Validate dataset integrity
python code/main.py --check-data

# Evaluate a single request
python code/main.py --request request_01
```

---

## 13. Running Test Suite

Execute the complete automated test suite (131 unit and integration tests across 18 test files):

```bash
# From the project root
python -m pytest code/tests -v
```

---

## 14. Generating `output.csv`

To execute the evaluation pipeline across all 250 test requests and generate `output.csv`:

```bash
python code/main.py --evaluate
```

This will:
1. Reconstruct financial state and evidence for all 250 requests.
2. Execute 90-day cash flow simulations.
3. Compute `amount_safe_to_pay` and `earliest_date_for_full_payment`.
4. Generate, rank, and select optimal candidate plans.
5. Produce `output.csv` at the repository root and validate schema compliance.

---

## 15. Generating `usage_report.md`

`usage_report.md` is automatically refreshed during pipeline evaluation at `code/evaluation/usage_report.md`:

```bash
python code/main.py --evaluate
```

The report details model calls, execution time, token metrics ($0$ tokens for deterministic simulation), and cost breakdown ($$0.00$ USD).

---

## 16. Environment Variables

The core solution runs fully offline and deterministically without requiring external API keys. Optional configuration variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATASET_DIR` | `dataset/` | Custom path to dataset folder |
| `OUTPUT_PATH` | `output.csv` | Destination path for output predictions |
| `REPORT_PATH` | `code/evaluation/usage_report.md` | Destination path for usage report |
| `PYTHONPATH` | `code` | Python module resolution path |

---

## 17. Known Limitations

1. **Fixed Historical FX Rates**: Currency conversions rely strictly on dated entries in `dataset/exchange_rates.csv`. If an unrecorded foreign currency pair date is requested, the event cannot enter cash state (no speculative live rate fetching).
2. **90-Day Simulation Horizon**: Cash flow forecasting is bounded to $90$ calendar days from `request_date`. Commitments beyond day 90 are not projected.
3. **Monthly Cadence Assumption**: Recurring subscriptions and debits default to monthly cadence unless explicit historical gap intervals dictate otherwise.
4. **Max 3 Spending Changes**: In accordance with competition rules, the spending change optimizer explores combinations up to size 3.

