"""FastAPI web layer for Buy or Wait? financial decision engine.

This is a thin HTTP transport layer that directly invokes the existing tested backend
pipeline without reimplementing or duplicating any financial logic.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

# Import existing backend modules directly
from config import DEFAULT_DATASET_DIR
from data_loader import DataLoader
from decision_agent import DecisionAgent
from financial_state_service import FinancialStateService
from forecast_engine import ForecastEngine, ProposedPayment
from models import FinancialProfile, FinancialRequest, OutputRow
from resilience_analysis import ResilienceAnalyzer
from time_machine import FinancialTimeMachine


app = FastAPI(
    title="Buy or Wait? Financial Decision API",
    description="Thin API layer over the deterministic 90-day cashflow decision engine with witty sarcastic voice responses.",
    version="1.0.0",
)

# Configure CORS Middleware
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if frontend_url and frontend_url not in origins:
    origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exact Sarcastic LLM System Prompt with Anti-Cliché & Variety Directives
SARCASTIC_FINANCIAL_SYSTEM_PROMPT = """You are a sharp-tongued, sarcastic personal finance assistant. You will be given the real computed decision (affordable or not, exact numbers in ₹, dates) from a deterministic financial engine — never invent numbers, only use what's provided.

Deliver the verdict in a witty, sarcastic, slightly dramatic tone — like a brutally honest friend who's seen your bank statement and isn't impressed, but still actually helps.

Rules:
- Avoid AI-cliché phrasing entirely. Do NOT use these overused patterns: 'Well well, look who...', 'Buddy...', starting every negative response with 'Absolutely not', or any repeated sentence skeleton across different answers. Each response should feel freshly written, not filled into a template.
- Vary your approach each time — sometimes open with a blunt fact, sometimes with a rhetorical question, sometimes with a mock-serious tone, sometimes with a one-word reaction before continuing. Reference specific, unexpected details from the REAL numbers given (exact rupee amounts, exact dates, how many days until trouble hits) rather than vague drama.
- Write like a real witty friend texting back, not like a comedian doing a bit. Keep it conversational, occasionally blunt, sometimes dry rather than always over-the-top. Not every response needs a joke — sometimes a sharp, short observation lands better than an elaborate metaphor.
- Avoid generic filler phrases like 'live a little', 'practically responsible of you', 'more of a suggestion' — these are becoming crutches. Generate fresh wording every time based on the actual numbers, never reuse a phrase you've used before in this conversation.
- If affordable: deliver approval with dry, genuine wit or mock-disbelief, but keep it grounded in the exact numbers.
- If NOT affordable: deliver the bad news with dramatic flair or dry reality, but always end with real actionable numbers (earliest safe date, amount safe to spend now). Never be cruel about the person, only sarcastic about the purchase decision.
- Always ground every remark in the real numbers given. Never invent consequences not reflected in the actual forecast data.
- Keep responses under 4 sentences — this will be spoken aloud via text-to-speech."""



# Singletons for loaded dataset and services
class EngineContext:
    def __init__(self, dataset_dir: Path):
        self.dataset_dir = dataset_dir
        self.loader = DataLoader(dataset_dir)
        self.ctx = self.loader.load_all()
        self.agent = DecisionAgent(dataset_dir)
        self.state_service = FinancialStateService(dataset_dir)
        self.time_machine = FinancialTimeMachine()
        self.resilience_analyzer = ResilienceAnalyzer()


ctx_holder: EngineContext | None = None


def get_ctx() -> EngineContext:
    global ctx_holder
    if ctx_holder is None:
        ctx_holder = EngineContext(DEFAULT_DATASET_DIR)
    return ctx_holder


# Request and Response Models
class EvaluateRequest(BaseModel):
    user_id: str = Field(default="user_07", description="User ID for financial profile")
    item_name: str = Field(default="Expense", description="Name or description of the item")
    amount: Decimal = Field(..., gt=0, description="Requested purchase/expense amount in INR")
    request_date: date | None = Field(default=None, description="Date of evaluation (YYYY-MM-DD)")
    desired_completion_date: date | None = Field(
        default=None, description="Desired completion deadline (YYYY-MM-DD)"
    )
    allows_partial_payment: bool = Field(default=True, description="Whether partial payment is allowed")
    request_type: str = Field(default="purchase", description="Category of financial request")
    request_id: str | None = Field(default=None, description="Optional request ID if evaluating an existing dataset request")
    request_text: str | None = Field(default=None, description="Original query text")


class DecisionResponse(BaseModel):
    request_id: str
    currency: str = "INR"
    amount_safe_to_pay: str
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str | None
    spending_changes_needed: str
    decision_explanation: str
    sarcastic_explanation: str | None = None


class VoiceQueryRequest(BaseModel):
    query: str = Field(..., description="Transcribed speech query from Web Speech API")
    user_id: str = Field(default="user_07", description="User ID")


class VoiceQueryResponse(BaseModel):
    query: str
    currency: str = "INR"
    extracted_intent: dict[str, Any]
    verdict: str
    spoken_response: str
    decision: DecisionResponse


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "buy-or-wait-api", "currency": "INR"}


def _generate_sarcastic_voice_response(
    query: str,
    item_name: str,
    amount: Decimal,
    currency: str,
    decision: DecisionResponse,
) -> str:
    """Deliver the deterministic decision using the sarcastic LLM system prompt."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            user_prompt = f"""User query: "{query}"
Deterministic Financial Output:
- Item: {item_name}
- Requested Amount: ₹{amount}
- Affordability Status: {decision.affordability_status}
- Recommended Payment Method: {decision.recommended_payment_method}
- Amount Safe To Pay Today: ₹{decision.amount_safe_to_pay}
- Earliest Safe Date: {decision.earliest_date_for_full_payment or 'N/A'}
- Payment Plan: {decision.payment_plan}
- Spending Changes Needed: {decision.spending_changes_needed}
- Fact-based Explanation: "{decision.decision_explanation}"

Deliver the verdict in your witty, sarcastic tone adhering strictly to all anti-cliché rules in your system instructions."""

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SARCASTIC_FINANCIAL_SYSTEM_PROMPT,
                    temperature=0.85,
                ),
            )
            if response.text and len(response.text.strip()) > 0:
                return response.text.strip()
        except Exception as e:
            print(f"[LLM] Sarcastic generation error: {e}, using witty fallback.")

    # Dynamic, anti-cliché response generation grounded strictly in deterministic numbers
    safe_amt_dec = Decimal(str(decision.amount_safe_to_pay))
    date_str = decision.earliest_date_for_full_payment or "next month"

    if decision.affordability_status == "affordable_now":
        if amount <= 500:
            return f"It's ₹{amount}. Your account won't even flinch, and your reserve floor stays completely safe."
        else:
            return f"₹{amount} for {item_name} is cleared to go today. You'll keep your safety cushion fully intact with zero stress."
    elif decision.affordability_status == "affordable_with_plan":
        return f"Dropping ₹{amount} at once would pinch, but splitting it into {decision.payment_plan} keeps your balance above the line."
    elif decision.affordability_status == "affordable_later":
        diff = amount - safe_amt_dec
        if diff <= 15000:
            return f"You're just ₹{diff:,.0f} shy of paying ₹{amount:,.0f} for {item_name} today without hitting your reserve limit. Hold off until {date_str} and you're good."
        else:
            return f"₹{amount:,.0f} right now? Not happening. You've got ₹{safe_amt_dec:,.0f} in safe headroom today, so wait until {date_str} for the full amount."
    else:
        return f"Hard pass on {item_name}. At ₹{amount:,.0f}, this crashes right through your reserve floor. Your actual safe limit today is ₹{safe_amt_dec:,.0f}."


@app.post("/api/evaluate", response_model=DecisionResponse)
def evaluate_request(payload: EvaluateRequest) -> DecisionResponse:
    """Evaluate whether a user can safely afford an expense."""
    ctx = get_ctx()

    # Check if this matches a known request in the dataset
    req: FinancialRequest | None = None
    if payload.request_id:
        req = ctx.ctx.requests_by_id.get(payload.request_id) or ctx.ctx.sample_requests_by_id.get(payload.request_id)

    if req is None:
        profile = ctx.ctx.profiles_by_user.get(payload.user_id)
        if profile is None:
            raise HTTPException(status_code=404, detail=f"User profile '{payload.user_id}' not found.")

        req_date = payload.request_date or date(2024, 3, 3)
        comp_date = payload.desired_completion_date or (req_date + timedelta(days=30))
        req_id = payload.request_id or f"req_dynamic_{uuid.uuid4().hex[:8]}"
        req_text = payload.request_text or f"Can I afford {payload.item_name} for ₹{payload.amount}?"

        req = FinancialRequest(
            request_id=req_id,
            user_id=payload.user_id,
            request_date=req_date,
            request_type=payload.request_type,
            requested_amount=payload.amount,
            desired_completion_date=comp_date,
            allows_partial_payment=payload.allows_partial_payment,
            request_text=req_text,
        )

        dict_entry = {
            "request_id": req_id,
            "user_id": req.user_id,
            "request_date": req.request_date.isoformat(),
            "request_type": req.request_type,
            "requested_amount": str(req.requested_amount),
            "desired_completion_date": req.desired_completion_date.isoformat(),
            "allows_partial_payment": "true" if req.allows_partial_payment else "false",
            "request_text": req.request_text,
        }
        ctx.state_service._requests_by_id[req_id] = dict_entry
        ctx.agent.state_service._requests_by_id[req_id] = dict_entry

    # Evaluate using existing deterministic DecisionAgent
    # For dynamic API requests, ensure full_payment is allowed alongside profile preferences
    is_dynamic = (payload.request_id is None) or (
        payload.request_id not in ctx.ctx.requests_by_id and payload.request_id not in ctx.ctx.sample_requests_by_id
    )

    orig_profile = ctx.agent._profiles.get(req.user_id)
    if is_dynamic and orig_profile is not None:
        methods = list(orig_profile.payment_methods_user_will_consider)
        if "full_payment" not in methods:
            methods.append("full_payment")
        dynamic_profile = FinancialProfile(
            user_id=orig_profile.user_id,
            home_currency=orig_profile.home_currency,
            current_available_balance=orig_profile.current_available_balance,
            minimum_balance_to_keep=orig_profile.minimum_balance_to_keep,
            financial_priorities=orig_profile.financial_priorities,
            expense_categories_to_protect=orig_profile.expense_categories_to_protect,
            expense_categories_user_is_willing_to_reduce=orig_profile.expense_categories_user_is_willing_to_reduce,
            expense_categories_user_is_willing_to_stop=orig_profile.expense_categories_user_is_willing_to_stop,
            payment_methods_user_will_consider=tuple(methods),
            max_installment_months=orig_profile.max_installment_months,
        )
        ctx.agent._profiles[req.user_id] = dynamic_profile
        try:
            out_row: OutputRow = ctx.agent.evaluate_request(req)
        finally:
            ctx.agent._profiles[req.user_id] = orig_profile
    else:
        out_row = ctx.agent.evaluate_request(req)

    # Deliver formatted explanation
    clean_explanation = out_row.decision_explanation
    for c in ["ZAR", "EUR", "USD", "IDR"]:
        clean_explanation = clean_explanation.replace(f"{c} ", "₹").replace(c, "INR")

    temp_response = DecisionResponse(
        request_id=out_row.request_id,
        currency="INR",
        amount_safe_to_pay=str(out_row.amount_safe_to_pay),
        affordability_status=out_row.affordability_status,
        recommended_payment_method=out_row.recommended_payment_method,
        payment_plan=out_row.payment_plan,
        earliest_date_for_full_payment=(
            out_row.earliest_date_for_full_payment.isoformat()
            if out_row.earliest_date_for_full_payment
            else None
        ),
        spending_changes_needed=out_row.spending_changes_needed,
        decision_explanation=clean_explanation,
    )

    # Generate sarcastic natural language verdict using the shared prompt
    effective_amount = payload.amount if payload.amount is not None else req.requested_amount
    effective_item = payload.item_name if payload.item_name != "Expense" else (req.request_text or payload.item_name)
    query_text = payload.request_text or f"Can I afford {effective_item} for ₹{effective_amount}?"
    sarcastic_text = _generate_sarcastic_voice_response(
        query=query_text,
        item_name=effective_item,
        amount=effective_amount,
        currency="INR",
        decision=temp_response,
    )

    temp_response.decision_explanation = sarcastic_text
    temp_response.sarcastic_explanation = sarcastic_text

    return temp_response


@app.get("/api/time-machine/{request_id}")
def get_time_machine_scenarios(request_id: str) -> dict[str, Any]:
    """Return 90-day time machine scenarios (BUY_NOW, WAIT, PARTIAL_PAYMENT, INSTALLMENTS)."""
    ctx = get_ctx()

    req = ctx.ctx.requests_by_id.get(request_id) or ctx.ctx.sample_requests_by_id.get(request_id)
    if req is None:
        raw = ctx.state_service._requests_by_id.get(request_id)
        if raw is None:
            raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
        req = FinancialRequest(
            request_id=raw["request_id"],
            user_id=raw["user_id"],
            request_date=datetime.strptime(raw["request_date"], "%Y-%m-%d").date(),
            request_type=raw.get("request_type", "purchase"),
            requested_amount=Decimal(raw["requested_amount"]),
            desired_completion_date=datetime.strptime(raw["desired_completion_date"], "%Y-%m-%d").date(),
            allows_partial_payment=raw.get("allows_partial_payment", "true").lower() == "true",
            request_text=raw.get("request_text", ""),
        )

    profile = ctx.ctx.profiles_by_user.get(req.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User profile for '{req.user_id}' not found.")

    state = ctx.state_service.reconstruct(request_id)
    messages = [m.__dict__ for m in ctx.ctx.messages_by_user.get(req.user_id, [])]
    options = ctx.ctx.options_by_request.get(request_id, [])

    scenarios = ctx.time_machine.simulate_all_scenarios(
        request=req,
        profile=profile,
        state=state,
        payment_options=options,
        user_messages=messages,
    )

    return {
        "request_id": request_id,
        "user_id": req.user_id,
        "currency": "INR",
        "available_balance": str(state.available_balance),
        "minimum_balance_to_keep": str(state.minimum_balance_to_keep),
        "requested_amount": str(req.requested_amount),
        "scenarios": [
            {
                "scenario_name": s.scenario_name,
                "is_safe": s.is_safe,
                "lowest_balance": str(s.lowest_balance),
                "lowest_balance_date": s.lowest_balance_date.isoformat() if s.lowest_balance_date else None,
                "safety_margin": str(s.safety_margin),
                "completion_date": s.completion_date.isoformat() if s.completion_date else None,
                "total_amount_paid": str(s.total_amount_paid),
                "number_of_payments": s.number_of_payments,
                "payments": [
                    {"date": p.payment_date.isoformat(), "amount": str(p.amount)}
                    for p in s.payments
                ],
            }
            for s in scenarios
        ],
    }


@app.get("/api/resilience/{request_id}")
def get_resilience_analysis(
    request_id: str,
    unexpected_expense: Decimal | None = Query(default=None, description="Optional shock debit amount"),
) -> dict[str, Any]:
    """Return cash-flow stress test report across salary delay and unexpected expense shocks."""
    ctx = get_ctx()

    req = ctx.ctx.requests_by_id.get(request_id) or ctx.ctx.sample_requests_by_id.get(request_id)
    if req is None:
        raw = ctx.state_service._requests_by_id.get(request_id)
        if raw is None:
            raise HTTPException(status_code=404, detail=f"Request '{request_id}' not found.")
        req = FinancialRequest(
            request_id=raw["request_id"],
            user_id=raw["user_id"],
            request_date=datetime.strptime(raw["request_date"], "%Y-%m-%d").date(),
            request_type=raw.get("request_type", "purchase"),
            requested_amount=Decimal(raw["requested_amount"]),
            desired_completion_date=datetime.strptime(raw["desired_completion_date"], "%Y-%m-%d").date(),
            allows_partial_payment=raw.get("allows_partial_payment", "true").lower() == "true",
            request_text=raw.get("request_text", ""),
        )

    profile = ctx.ctx.profiles_by_user.get(req.user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"User profile for '{req.user_id}' not found.")

    out_row: OutputRow = ctx.agent.evaluate_request(req)
    state = ctx.state_service.reconstruct(request_id)

    plan_payments: list[ProposedPayment] = []
    if out_row.payment_plan != "none":
        for part in out_row.payment_plan.split("|"):
            if ":" in part:
                d_str, amt_str = part.split(":", 1)
                plan_payments.append(
                    ProposedPayment(
                        payment_date=datetime.strptime(d_str.strip(), "%Y-%m-%d").date(),
                        amount=Decimal(amt_str.strip()),
                    )
                )

    messages = [m.__dict__ for m in ctx.ctx.messages_by_user.get(req.user_id, [])]

    report = ctx.resilience_analyzer.analyze_plan_resilience(
        state=state,
        plan_payments=tuple(plan_payments),
        unexpected_expense_amount=unexpected_expense,
        user_messages=messages,
    )

    return {
        "request_id": request_id,
        "user_id": req.user_id,
        "currency": "INR",
        "recommended_method": out_row.recommended_payment_method,
        "affordability_status": out_row.affordability_status,
        "payment_plan": out_row.payment_plan,
        "is_baseline_safe": report.is_baseline_safe,
        "baseline_safety_margin": str(report.baseline_safety_margin),
        "stress_results": [
            {
                "stress_test_name": res.stress_test_name,
                "is_safe": res.is_safe,
                "lowest_balance": str(res.lowest_balance),
                "lowest_balance_date": res.lowest_balance_date.isoformat() if res.lowest_balance_date else None,
                "safety_margin": str(res.safety_margin),
                "description": res.description,
            }
            for res in report.stress_results
        ],
    }


def _extract_intent_via_llm_or_fallback(query: str) -> dict[str, Any]:
    """Extract item, amount, and urgency strictly as JSON intent without computing math."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gemini_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=gemini_key)
            prompt = (
                "Extract structured purchase intent parameters from the user's query into pure JSON.\n"
                "Do NOT perform any financial calculations or affordability math.\n"
                "Return a JSON object with keys: item_name (string), amount (number), urgency (string: 'immediate' | 'soon' | 'flexible').\n"
                f"Query: \"{query}\""
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            if response.text:
                data = json.loads(response.text)
                return {
                    "item_name": data.get("item_name", "Item"),
                    "amount": Decimal(str(data.get("amount", 100))),
                    "urgency": data.get("urgency", "immediate"),
                }
        except Exception as e:
            print(f"[VoiceQuery] Intent extraction error: {e}, using fallback.")

    # Robust regex fallback
    amount_match = re.search(r"(?:for|\$|€|£|₹|zar|idr|eur|usd|inr)?\s*(\d+[\d,]*\.?\d*)", query, re.IGNORECASE)
    amount_val = Decimal("100")
    if amount_match:
        try:
            cleaned = amount_match.group(1).replace(",", "")
            if cleaned:
                amount_val = Decimal(cleaned)
        except Exception:
            pass

    item_name = "Item"
    item_match = re.search(r"(?:buy|afford|purchase|get|pay for)\s+(?:a|an|the)?\s*([a-zA-Z0-9\s]+?)(?:\s+for|\s+today|\s+now|\s+this|\?|$)", query, re.IGNORECASE)
    if item_match:
        item_name = item_match.group(1).strip()

    return {
        "item_name": item_name.capitalize(),
        "amount": amount_val,
        "urgency": "immediate" if ("today" in query.lower() or "now" in query.lower()) else "soon",
    }


@app.post("/api/voice-query", response_model=VoiceQueryResponse)
def handle_voice_query(payload: VoiceQueryRequest) -> VoiceQueryResponse:
    """Process transcribed voice queries, extract structured intent, run deterministic engine, and respond sarcastically."""
    user_id = payload.user_id or "user_07"
    currency = "INR"

    # 1. Extract structured intent via LLM (No financial math allowed in LLM)
    extracted = _extract_intent_via_llm_or_fallback(payload.query)

    # 2. Feed structured intent into deterministic evaluation engine
    eval_req = EvaluateRequest(
        user_id=user_id,
        item_name=extracted["item_name"],
        amount=extracted["amount"],
        request_date=date(2024, 9, 5),
        desired_completion_date=date(2024, 11, 14),
        request_text=payload.query,
    )
    decision = evaluate_request(eval_req)

    # 3. Deliver deterministic verdict using sarcastic system prompt
    spoken = decision.decision_explanation

    if decision.affordability_status == "affordable_now":
        verdict = "BUY_NOW"
    elif decision.affordability_status == "affordable_with_plan":
        verdict = "AFFORDABLE_WITH_PLAN"
    elif decision.affordability_status == "affordable_later":
        verdict = "WAIT"
    else:
        verdict = "NOT_RECOMMENDED"

    return VoiceQueryResponse(
        query=payload.query,
        extracted_intent={
            "item_name": extracted["item_name"],
            "amount": str(extracted["amount"]),
            "urgency": extracted["urgency"],
        },
        verdict=verdict,
        spoken_response=spoken,
        decision=decision,
    )


