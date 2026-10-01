import React, { useState, useEffect } from 'react';
import {
  CurrencySelectorPill,
  PrimaryButton,
  DarkSectionCard,
  Card,
  OutlinedButton,
  FeatureRow,
  FallingCoins,
} from '../components';
import { evaluateRequest } from '../api';
import { parseDecisionFactors } from '../utils/explanationParser';
import { formatINR } from '../utils/currencyFormatter';
import { AlertTriangle, ArrowRight } from 'lucide-react';

export function DecisionPage({ initialParams, onNavigate }) {
  const [itemName, setItemName] = useState(initialParams?.item || 'OnePlus 12 Smartphone');
  const [amount, setAmount] = useState(initialParams?.amount || '64999');
  const [allowsPartial, setAllowsPartial] = useState(true);
  const [requestId, setRequestId] = useState(initialParams?.request_id || '');

  const [loading, setLoading] = useState(false);
  const [decision, setDecision] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (initialParams?.amount && initialParams?.item) {
      handleEvaluate();
    }
  }, []);

  const handleEvaluate = async (e) => {
    if (e) e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount greater than ₹0.');
      return;
    }

    setLoading(true);
    setError(null);
    setDecision(null);

    try {
      const payload = {
        user_id: 'user_07', // Native INR user profile from benchmark dataset
        item_name: itemName || 'Requested Purchase',
        amount: parseFloat(amount),
        allows_partial_payment: allowsPartial,
        request_type: 'purchase',
        request_id: requestId || undefined,
      };

      const result = await evaluateRequest(payload);
      setDecision(result);
    } catch (err) {
      setError(err.message || 'An error occurred while evaluating affordability.');
    } finally {
      setLoading(false);
    }
  };

  const isAffordable =
    decision &&
    (decision.affordability_status === 'affordable_now' ||
      decision.affordability_status === 'affordable_with_plan');

  const verdictHeadline = !decision
    ? ''
    : decision.affordability_status === 'affordable_now'
    ? 'SAFE TO BUY NOW'
    : decision.affordability_status === 'affordable_with_plan'
    ? 'AFFORDABLE WITH PLAN'
    : decision.affordability_status === 'affordable_later'
    ? 'WAIT FOR SAFE DATE'
    : 'NOT RECOMMENDED';

  const verdictStatusType = isAffordable ? 'safe' : 'danger';

  return (
    <div className="space-y-10 py-6 max-w-[1000px] mx-auto">
      {/* Header Section */}
      <section className="text-center">
        <p className="text-micro font-bold uppercase tracking-wider text-pebble mb-2">
          Affordability Decision Engine
        </p>
        <h1 className="font-display-wise text-subheading md:text-heading text-forest-ink leading-[1.05]">
          CAN YOU SAFELY AFFORD THIS?
        </h1>
        <p className="mt-3 text-body text-charcoal max-w-xl mx-auto">
          Evaluate any purchase against your 90-day cashflow, scheduled commitments, and protected minimum balance floor.
        </p>
      </section>

      {/* Decision Input Form */}
      <section className="rounded-cards bg-fog p-6 md:p-8 shadow-subtle">
        <form onSubmit={handleEvaluate} className="space-y-6">
          <div className="flex items-center justify-between pb-2">
            <span className="text-caption font-bold text-forest-ink">
              Purchase Details
            </span>

            <label className="inline-flex items-center gap-2 cursor-pointer text-caption font-medium text-charcoal">
              <input
                type="checkbox"
                checked={allowsPartial}
                onChange={(e) => setAllowsPartial(e.target.checked)}
                className="h-4 w-4 rounded text-forest-ink focus:ring-forest-ink cursor-pointer"
              />
              Allow Partial / Installment Plans
            </label>
          </div>

          {/* Currency Selector Pill Style Input (INR Only) */}
          <CurrencySelectorPill
            itemName={itemName}
            onItemNameChange={setItemName}
            amount={amount}
            onAmountChange={setAmount}
            placeholderItem="e.g. OnePlus 12 / MacBook Air"
            placeholderAmount="64999"
          />

          {/* Submit CTA */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
            <div className="text-micro text-slate">
              <span>90-Day safety check applied automatically</span>
            </div>
            <PrimaryButton type="submit" disabled={loading} className="w-full sm:w-auto px-8 py-3 text-body-sm">
              {loading ? 'Simulating 90-Day Cashflow...' : 'Check Affordability'}
            </PrimaryButton>
          </div>
        </form>

        {error && (
          <div className="mt-4 rounded-[10px] bg-alarm-red/10 p-4 text-caption font-medium text-alarm-red border border-alarm-red/20 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {/* Verdict Output: Rendered in Dark Section Card per DESIGN.md */}
      {decision && (
        <section className="animate-verdict-slide-in space-y-8">
          <DarkSectionCard
            headline={verdictHeadline}
            statusType={verdictStatusType}
            subtitle={`Evaluation for ${itemName || 'Requested Item'} (${formatINR(amount)})`}
          >
            {/* Animated Falling Coins on verdict trigger */}
            <FallingCoins key={decision.request_id || JSON.stringify(decision)} count={5} />

            {/* Full Decision Explanation */}
            <div className="rounded-[10px] bg-paper/10 backdrop-blur-sm p-6 border border-paper/15 text-paper mb-6">
              <span className="text-micro font-bold uppercase tracking-wider text-lime-voltage block mb-2">
                Deterministic Decision Verdict
              </span>
              <p className="text-body leading-relaxed font-normal">
                {decision.decision_explanation}
              </p>
            </div>

            {/* Inset White Card for Metrics Breakdown */}
            <div className="rounded-cards bg-paper p-6 text-charcoal shadow-lg">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                  <span className="text-micro font-bold uppercase text-pebble block">Amount Safe Today</span>
                  <p className="text-body-lg font-bold text-forest-ink mt-1">
                    {formatINR(decision.amount_safe_to_pay || 0)}
                  </p>
                </div>

                <div>
                  <span className="text-micro font-bold uppercase text-pebble block">Recommended Method</span>
                  <p className="text-body-lg font-bold text-obsidian capitalize mt-1">
                    {decision.recommended_payment_method?.replace(/_/g, ' ')}
                  </p>
                </div>

                <div>
                  <span className="text-micro font-bold uppercase text-pebble block">Earliest Safe Date</span>
                  <p className="text-body-lg font-bold text-forest-ink mt-1">
                    {decision.earliest_date_for_full_payment || 'N/A (Exceeds Horizon)'}
                  </p>
                </div>

                <div>
                  <span className="text-micro font-bold uppercase text-pebble block">Spending Changes</span>
                  <p className="text-body-lg font-bold text-charcoal mt-1">
                    {decision.spending_changes_needed === 'none' ? 'None Required' : decision.spending_changes_needed}
                  </p>
                </div>
              </div>

              {/* Payment Schedule Pills */}
              {decision.payment_plan && decision.payment_plan !== 'none' && (
                <div className="mt-6 pt-6 border-t border-fog">
                  <span className="text-micro font-bold uppercase text-pebble block mb-3">
                    Recommended Payment Schedule
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {decision.payment_plan.split('|').map((part, idx) => {
                      const [pDate, pAmt] = part.split(':');
                      return (
                        <div
                          key={idx}
                          className="rounded-full bg-linen-mist px-4 py-2 text-caption font-bold text-forest-ink flex items-center gap-2 border border-lime-voltage/30"
                        >
                          <span className="text-micro font-normal text-slate">{pDate}</span>
                          <span>{formatINR(pAmt)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Time Machine Jump Action */}
              <div className="mt-6 pt-4 flex items-center justify-between border-t border-fog">
                <span className="text-caption text-slate">
                  Simulate all scenarios in Financial Time Machine
                </span>
                <OutlinedButton
                  onClick={() =>
                    onNavigate('time-machine', {
                      requestId: decision.request_id,
                    })
                  }
                  className="flex items-center gap-2"
                >
                  Explore in Time Machine <ArrowRight className="h-4 w-4" />
                </OutlinedButton>
              </div>
            </div>
          </DarkSectionCard>

          {/* Feature Row-style Panel Below Verdict Card per DESIGN.md */}
          <FeatureRow
            factors={parseDecisionFactors(decision)}
            title="Key Decision Factors"
          />
        </section>
      )}
    </div>
  );
}

export default DecisionPage;
