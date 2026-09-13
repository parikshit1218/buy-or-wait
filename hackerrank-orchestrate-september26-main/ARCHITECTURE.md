# Buy or Wait? System Architecture

Architectural specification and design document for the HackerRank Orchestrate (September 2026) **"Buy or Wait?"** financial decision system.

---

## 1. Project Goal & Contract Requirements

The objective is to construct a deterministic, production-grade financial reasoning agent that produces exactly one row in `./output.csv` for every evaluation request in `dataset/requests.csv` (250 rows).

### 1.1 Non-Negotiable Contract
1. **Output Location & Header**: Must write `./output.csv` at the repository root with the exact header:
   ```text
   request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
   ```
2. **Safety Invariant**:
   For any recommended plan, the simulated balance must satisfy:
   $$\text{balance}(t) \ge \text{minimum\_balance\_to\_keep}, \quad \forall t \in [\text{request\_date}, \text{request\_date} + 90]$$
3. **Amount Bounds**:
   $$0 \le \text{amount\_safe\_to\_pay} \le \text{requested\_amount}$$
4. **Permitted Statuses & Methods**:
   - `affordability_status` $\in$ {`affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable`}
   - `recommended_payment_method` $\in$ {`full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended`}
5. **No Synthetic Extrapolations**:
   No external API calls, live market data, inverted forex rates, or unsubstantiated income/debit creation. All missing amounts must be grounded in the supplied images.

---

## 2. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Data Layer [Data Layer: dataset/]
        CSV[CSV Tables: profiles, events, requests, options, rates, messages, images]
        Media[Media PNGs: image_01 to image_16]
    end

    subgraph Ingestion & Evidence Resolution
        Loader[Data Ingestion & Normalizer]
        ImgRes[Image Amount Resolver]
        MsgInt[Message Interpreter]
        Forex[Currency Conversion Service]
    end

    subgraph State Reconstruction & Simulation
        Recon[Financial State Reconstruction Service]
        Sim[90-Day Simulation & Forecast Engine]
        SafeCalc[Safe-Now Calculator]
        EarlyCalc[Earliest Full Payment Service]
    end

    subgraph Plan Optimization & Ranking
        Gen[Candidate Plan Generator: Full, Partial, Installments, Wait]
        SpendOpt[Spending Change Optimizer: stop / reduce_to]
        Ranker[Multi-Criteria Plan Ranking Engine]
        Val[Feasibility & Invariant Validator]
    end

    subgraph Presentation & Evaluation
        Expl[Decision Explanation Generator]
        Exporter[CSV Output Exporter: root ./output.csv]
        Usage[Token Usage Reporter: evaluation/usage_report.md]
    end

    Data Layer --> Ingestion & Evidence Resolution
    Ingestion & Evidence Resolution --> State Reconstruction & Simulation
    State Reconstruction & Simulation --> Plan Optimization & Ranking
    Plan Optimization & Ranking --> Presentation & Evaluation
```

---

## 3. Component Breakdown & Responsibilities

### 3.1 Data Ingestion & Type Normalizer
- Reads all 8 CSV tables with strict encoding (`utf-8`) and deterministic parsing.
- Casts monetary quantities to `Decimal` (avoiding floating-point inaccuracies).
- Parses dates to `datetime.date`.
- Enforces relational referential integrity across `user_id`, `request_id`, and `event_id`.

### 3.2 Evidence Resolution Layer
- **Image Amount Resolver**:
  - Resolves the 16 financial events with blank amounts via `images.csv` and `dataset/media/images/<image_id>.png`.
  - Employs a verified deterministic fallback table backed by OCR verification.
  - Never defaults a blank amount to zero.
- **Message Interpreter**:
  - Parses unstructured text from employers, banks, merchants, and service providers.
  - Extracts explicit cancellations, settlements, salary changes, and revised payment dates.
  - Neutralizes prompt-injection attempts and ignores instructions conflicting with core safety rules.
- **Currency Conversion Service**:
  - Exact lookup on `(settlement_date, from_currency, to_currency)` from `exchange_rates.csv`.
  - Strict: raises `MissingExchangeRateError` if no exact pair exists on that date; never inverts or triangulates.

### 3.3 Financial State Reconstruction Service
- Reconstructs user cash state starting from `current_available_balance` and `minimum_balance_to_keep`.
- **Conflict Resolution Precedence**:
  1. Explicit message evidence (cancellation, settlement, amendment).
  2. Newer record from same source.
  3. Settled status over scheduled/pending.
  4. Financially safer interpretation (higher debit, lower credit).
- **Cash Flow Classification**:
  - Pending debits: reserved immediately.
  - Pending credits, unconfirmed refunds, non-cash valuations, unrealized investments: excluded until settled.
  - Recurring income / salary: confirmed salary integrated on scheduled settlement dates.
  - Subscriptions / recurring debits: detected via monthly historical regularity ($\ge 3$ consecutive cycles).

### 3.4 90-Day Simulation & Forecast Engine
- Simulates daily end-of-day balances: $B(t) = B(t-1) + \sum \text{Credits}(t) - \sum \text{Debits}(t) - \sum \text{PlanPayments}(t)$.
- Projects regular recurring expenses forward across the 90-day window.
- **Double-Counting Guard**: If an actual scheduled event exists within $\pm 7$ days of a projected recurrence, the projection is suppressed.
- Verifies $\min_{t} B(t) \ge \text{minimum\_balance\_to\_keep}$.

### 3.5 Safe-Now & Earliest Date Calculators
- **`amount_safe_to_pay`**:
  - The maximum payment that can be made on `request_date` without spending changes such that the 90-day simulation remains safe throughout, bounded in $[0, \text{requested\_amount}]$.
- **`earliest_date_for_full_payment`**:
  - Iterates candidate date $d \in [\text{request\_date}, \text{request\_date} + 90]$.
  - Finds the first date where a single lump-sum payment of `requested_amount` passes the 90-day simulation without spending changes.
  - Returns `None` (empty string) if no such date exists within the 90-day horizon.

### 3.6 Candidate Plan Generator & Optimizer
Generates eligible candidates based on user preferences:
1. **Full Payment**:
   - Single payment on `request_date`.
   - Requires `full_payment` $\in$ `payment_methods_user_will_consider`.
2. **Partial Payment**:
   - Requires `allows_partial_payment == true` AND `partial_payment` $\in$ considered methods.
   - Requires $0 < \text{amount\_safe\_to\_pay} < \text{requested\_amount}$.
   - Requires $\text{earliest\_date\_for\_full\_payment} \le \text{desired\_completion\_date}$.
   - Format: `request_date:amount_safe_to_pay | earliest_date:(requested_amount - amount_safe_to_pay)`.
3. **Installments**:
   - Evaluates all offers in `request_payment_options.csv` with `payment_method == 'installments'`.
   - Filters out options exceeding `max_installment_months` or disallowed by user preferences.
   - Verifies all installment dates complete by `desired_completion_date` (or as permitted).
4. **Wait (Affordable Later)**:
   - Evaluated when full payment is not safe today but becomes safe on `earliest_date_for_full_payment` $\le \text{desired\_completion\_date}$, and user considers `full_payment`.
5. **Spending Change Optimization**:
   - When a plan is not safe out-of-the-box, evaluates up to 3 candidate adjustments (`stop:<event_id>` or `reduce_to:<event_id>:<amt>`).
   - Only considers non-protected, flexible events in user-permitted categories.
   - Mutually exclusive: stopping and reducing the same event is rejected.

### 3.7 Plan Ranking & Selection Engine
When multiple safe candidates exist, ranks them strictly according to the problem specification:
1. **Completion by Deadline**: Plan completes on or before `desired_completion_date`.
2. **Spending Changes**: Plans requiring **no spending changes** precede plans needing changes.
3. **Cost Minimization**: Minimize `total_payable_amount` (including financing fees).
4. **Earlier Start**: Plan whose first payment date is earlier.
5. **Fewer Payments**: Plan with fewer total payment transactions.
6. **Tie-Breaker**: Lowest `payment_option_id` (or natural plan priority).

### 3.8 Presentation & Reporting Layer
- **Explanation Generator**: Produces concise, grounded rationale citing exact amounts, currencies, completion dates, and minimum balance protection.
- **Output Exporter**: Writes `./output.csv` with exact column formatting.
- **Usage Reporter**: Emits `evaluation/usage_report.md` detailing token counts, model architectures, and estimated costs.

---

## 4. Algorithmic Specifications

### 4.1 Plan Selection Hierarchy
```text
Candidate Generation
  ├── Candidate: Full Payment (T_0)
  ├── Candidate: Partial Payment (T_0 + T_early)
  ├── Candidate: Installment Option 1..N
  ├── Candidate: Wait (T_early)
  └── Candidate: Full / Installments + Spending Changes
          │
          ▼
Filter by User Preferences (methods considered, max months, protected categories)
          │
          ▼
Simulate each on 90-Day Cash Flow (must preserve min_balance every day)
          │
          ▼
Sort safe candidates by:
  1. completes_by_deadline DESC
  2. spending_changes == 'none' DESC
  3. total_cost ASC
  4. first_payment_date ASC
  5. num_payments ASC
  6. payment_option_id ASC
          │
          ▼
Select top candidate (Fallback: 'not_affordable' / 'not_recommended')
```

---

## 5. 12-Hour Phased Implementation Plan

| Phase | Duration | Scope & Key Deliverables |
|---|---|---|
| **Phase 1: Foundations & Ingestion** | Hours 0 – 1.5 | • Setup project structure, data contracts, and typing.<br>• Implement robust CSV loaders with Decimal precision.<br>• Connect Image Amount Resolver and Message Interpreter. |
| **Phase 2: State Reconstruction & Simulation** | Hours 1.5 – 4.0 | • Complete `FinancialStateService` with conflict resolution and message-derived salary updates.<br>• Enhance `ForecastEngine` with recurring debit/credit simulation and double-counting protection.<br>• Implement `EarliestFullPaymentService` and `SafeNowCalculator`. |
| **Phase 3: Plan Generation & Optimization** | Hours 4.0 – 6.5 | • Implement candidate generation for full, partial, installments, and wait.<br>• Build `SpendingChangeOptimizer` for permitted flexible reductions/stops.<br>• Implement strict 6-tier ranking engine. |
| **Phase 4: Explanation & Calibration** | Hours 6.5 – 8.5 | • Build template-based grounded explanation generator.<br>• Calibrate against all 25 ground-truth records in `sample_requests.csv`.<br>• Achieve 100% accuracy on sample evaluation metrics. |
| **Phase 5: Full Evaluation & Packaging** | Hours 8.5 – 10.5 | • Run full inference across all 250 evaluation requests in `requests.csv`.<br>• Generate root-level `./output.csv` and execute rigorous format validation.<br>• Create `evaluation/usage_report.md` recording deterministic/model metrics. |
| **Phase 6: Final Verification & Delivery** | Hours 10.5 – 12.0 | • Run full unit test suite (`code/tests/`).<br>• Audit against edge cases and invariant constraints.<br>• Package submission artifact `code.zip` and final transcript logs. |
