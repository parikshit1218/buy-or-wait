/**
 * API client utility for Buy or Wait? backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

/**
 * Health check endpoint.
 * GET /api/health
 */
export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Evaluate a buy-or-wait financial decision.
 * POST /api/evaluate
 *
 * @param {Object} payload
 * @param {string} [payload.user_id]
 * @param {string} [payload.item_name]
 * @param {number|string} payload.amount
 * @param {string} [payload.request_date]
 * @param {string} [payload.desired_completion_date]
 * @param {boolean} [payload.allows_partial_payment]
 * @param {string} [payload.request_type]
 * @param {string} [payload.request_id]
 */
export async function evaluateRequest(payload) {
  const res = await fetch(`${API_BASE_URL}/api/evaluate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Evaluation failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Get 90-day time machine scenario comparisons for a request.
 * GET /api/time-machine/{request_id}
 *
 * @param {string} requestId
 */
export async function getTimeMachine(requestId) {
  const res = await fetch(`${API_BASE_URL}/api/time-machine/${encodeURIComponent(requestId)}`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Time machine simulation failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Get cash-flow resilience analysis stress-testing for a request.
 * GET /api/resilience/{request_id}?unexpected_expense=<number>
 *
 * @param {string} requestId
 * @param {number|string} [unexpectedExpense]
 */
export async function getResilience(requestId, unexpectedExpense) {
  let url = `${API_BASE_URL}/api/resilience/${encodeURIComponent(requestId)}`;
  if (unexpectedExpense !== undefined && unexpectedExpense !== null && unexpectedExpense !== '') {
    url += `?unexpected_expense=${encodeURIComponent(unexpectedExpense)}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Resilience analysis failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

/**
 * Send voice query transcribed text for LLM intent extraction and decision.
 * POST /api/voice-query
 *
 * @param {string} query
 * @param {string} [userId='user_01']
 */
export async function sendVoiceQuery(query, userId = 'user_01') {
  const res = await fetch(`${API_BASE_URL}/api/voice-query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      user_id: userId,
    }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Voice query failed: ${res.status} ${res.statusText}`);
  }
  return res.json();
}
