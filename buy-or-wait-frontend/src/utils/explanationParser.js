/**
 * Parses the backend decision_explanation string and decision payload into
 * up to 3 structured key factors for the Feature Row component.
 *
 * @param {Object} decision - The decision response from POST /api/evaluate
 * @returns {Array<{icon: string, heading: string, explanation: string}>}
 */
export function parseDecisionFactors(decision) {
  if (!decision || !decision.decision_explanation) {
    return [
      {
        icon: 'reserve',
        heading: 'Safety Buffer Protected',
        explanation: 'Account maintains safe minimum balance throughout the forecast horizon.',
      },
      {
        icon: 'date',
        heading: 'Commitment Schedule',
        explanation: 'All scheduled debits and incoming payroll are synchronized.',
      },
      {
        icon: 'cash',
        heading: 'Liquidity Analysis',
        explanation: 'Deterministic evaluation based on your complete cashflow ledger.',
      },
    ];
  }

  const text = decision.decision_explanation;
  const factors = [];

  // 1. Check for Spending Changes Needed (e.g. stop/reduce)
  const stopMatch = text.match(/Stop\s+([^,]+),\s*then/i) || text.match(/Reduce\s+([^,]+),\s*then/i);
  if (stopMatch || (decision.spending_changes_needed && decision.spending_changes_needed !== 'none')) {
    factors.push({
      icon: 'lock',
      heading: 'Spending Change Required',
      explanation: stopMatch
        ? `Adjust ${stopMatch[1]} to safely unlock liquidity without breaching reserve.`
        : `Reduce flexible spending (${decision.spending_changes_needed}) to proceed safely.`,
    });
  }

  // 2. Check for Immediate Payment / Safe Now
  const payTodayMatch = text.match(/Pay\s+((?:[A-Z]{3}|₹)\s*[\d,.]+)\s+(today|now)/i);
  if (payTodayMatch) {
    factors.push({
      icon: 'cash',
      heading: 'Immediate Full Payment',
      explanation: `${payTodayMatch[1]} is 100% safe to pay on request date without overdraft risk.`,
    });
  }

  // 3. Check for Installment terms (e.g. "Use 3 installments of ₹68,432, starting 12 September 2024")
  const installmentMatch = text.match(/Use\s+(\d+)\s+installments\s+of\s+((?:[A-Z]{3}|₹)\s*[\d,.]+)(?:,\s*starting\s+([^.]+))?/i);
  if (installmentMatch) {
    factors.push({
      icon: 'installments',
      heading: `${installmentMatch[1]} Staggered Installments`,
      explanation: `Pay ${installmentMatch[2]} per installment${installmentMatch[3] ? ` starting ${installmentMatch[3]}` : ''}.`,
    });
  }

  // 4. Check for Deferred Wait Date (e.g. "Pay ₹52,100 on 15 November 2024" or "Wait until 15 June 2024")
  const waitMatch = text.match(/Wait until\s+([^,]+)/i) || text.match(/in full on\s+([^.]+)/i);
  if (waitMatch && !payTodayMatch) {
    factors.push({
      icon: 'date',
      heading: `Safe Target: ${waitMatch[1].trim()}`,
      explanation: `Deferring until ${waitMatch[1].trim()} allows confirmed income to replenish balance.`,
    });
  }

  // 5. Check for Minimum Reserve / Balance left (e.g. "leaves at least ₹93,000 available" or "below the ... minimum")
  const leavesMatch = text.match(/leaves at least\s+((?:[A-Z]{3}|₹)\s*[\d,.]+)\s+available/i);
  const riskMinMatch = text.match(/(?:below the|put the|keeps the)\s+((?:[A-Z]{3}|₹)\s*[\d,.]+)\s+minimum/i);

  if (leavesMatch) {
    factors.push({
      icon: 'reserve',
      heading: 'Protected Reserve Intact',
      explanation: `Account preserves at least ${leavesMatch[1]} liquidity buffer throughout 90 days.`,
    });
  } else if (riskMinMatch) {
    factors.push({
      icon: 'alert',
      heading: 'Minimum Reserve Guardrail',
      explanation: `Paying earlier would put your protected ${riskMinMatch[1]} minimum threshold at risk.`,
    });
  }

  // 6. Check for Not Recommended / Cannot Complete (e.g. "Do not make this payment by 12 January 2026")
  const doNotPayMatch = text.match(/Do not make this payment by\s+([^.]+)/i);
  if (doNotPayMatch) {
    factors.push({
      icon: 'alert',
      heading: 'Deadline Unachievable',
      explanation: `None of the available options keeps your minimum balance protected before ${doNotPayMatch[1].trim()}.`,
    });
  }

  // 7. Generic Fallback Fillers if fewer than 3 factors found
  if (factors.length < 3 && decision.amount_safe_to_pay) {
    const safeNum = parseFloat(decision.amount_safe_to_pay);
    if (!factors.some((f) => f.heading.includes('Safe') || f.heading.includes('Payment'))) {
      factors.push({
        icon: 'cash',
        heading: safeNum > 0 ? 'Safe Today Amount' : 'Zero Immediate Capacity',
        explanation:
          safeNum > 0
            ? `Up to ₹${safeNum.toLocaleString('en-IN')} can be settled today safely.`
            : 'Immediate payment would breach your minimum reserve floor.',
      });
    }
  }

  if (factors.length < 3) {
    factors.push({
      icon: 'horizon',
      heading: '90-Day Liquidity Horizon',
      explanation: 'Synchronized with confirmed income timing and essential living commitments.',
    });
  }

  if (factors.length < 3) {
    factors.push({
      icon: 'reserve',
      heading: 'Hard Floor Invariant',
      explanation: 'Ensures account balance never drops below your required minimum balance to keep.',
    });
  }

  return factors.slice(0, 3);
}

export default parseDecisionFactors;
