// frontend/src/services/api.js
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export default API_BASE;

// Same host as API_BASE, just ws(s):// instead of http(s):// — used by the
// Ask call UI to reach /ws/voice.
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Distinguishes *why* a request failed so the UI can react correctly:
//   "network"    - fetch() itself threw: backend unreachable, offline,
//                   DNS/CORS failure. Not a validation problem — the
//                   request never even reached the server.
//   "validation" - HTTP 400: the server understood the request but
//                   rejected it (e.g. couldn't identify customer/amount
//                   from speech).
//   "not_found"  - HTTP 404.
//   "server"     - HTTP 5xx: the backend (or a call it made to Azure/
//                   Supabase) failed while handling a valid request.
export class ApiError extends Error {
  constructor(message, kind, status) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

async function apiFetch(path, options) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, options);
  } catch (networkErr) {
    // fetch() only throws for network-level failures (backend down,
    // offline, CORS, DNS) — never for a valid HTTP error response, so
    // this is unambiguously "we couldn't reach the server at all".
    throw new ApiError(
      "Could not reach the server. Check your connection and that the backend is running.",
      "network"
    );
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail || `Request failed (${res.status})`;
    const kind = res.status === 400 ? "validation" : res.status === 404 ? "not_found" : "server";
    throw new ApiError(detail, kind, res.status);
  }

  if (res.status === 204) return null;
  return res.json();
}

function jsonBody(obj) {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) };
}

// Send a recorded utterance (WAV blob) to Azure AI Speech for transcription.
export async function transcribeAudio(blob) {
  const formData = new FormData();
  formData.append("file", blob, "entry.wav");
  return apiFetch("/transcribe", { method: "POST", body: formData });
  // -> { success, filename, text, language }
}

// Undo a just-saved transaction.
export async function deleteTransaction(transactionId) {
  return apiFetch(`/transactions/${transactionId}`, { method: "DELETE" });
}

// Edit a past entry's amount and/or type.
export async function updateTransaction(transactionId, updates) {
  return apiFetch(`/transactions/${transactionId}`, {
    method: "PATCH",
    ...jsonBody(updates),
  });
  // -> { success, transaction }
}

// Extract customer/amount/type/date from raw text — DISPLAY ONLY, saves nothing.
export async function extractTransaction(text, language = "hi") {
  return apiFetch("/extract", {
    method: "POST",
    ...jsonBody({ text, language }),
  });
  // -> { success, customer, amount, type, date, language }
}

// Actually extracts AND saves — call this only after the shopkeeper confirms
// (or, for the auto-save entry flow, when extraction confidence is high).
export async function processTransaction(text, language, shopkeeperId) {
  return apiFetch("/process-transaction", {
    method: "POST",
    ...jsonBody({ text, language, shopkeeper_id: shopkeeperId }),
  });
  // -> { success, customer_created, customer, transaction }
}

// ---------- Ledger & Risk screens ----------

// Every customer with balance + risk, plus "You'll Get / You'll Give" totals.
export async function getDashboardSummary(shopkeeperId) {
  return apiFetch(`/dashboard/summary?shopkeeper_id=${encodeURIComponent(shopkeeperId)}`);
  // -> { totals, risk_counts, customers: [...] }
}

// All entries (udhaar + payments) for one customer.
export async function getCustomerLedger(customerId) {
  return apiFetch(`/customers/${encodeURIComponent(customerId)}/ledger`);
  // -> { customer_id, transactions: [...] }
}

// Ready-to-send payment reminder text.
export async function generateReminder(shopkeeperId, customerId, tone, language) {
  return apiFetch("/dashboard/reminder", {
    method: "POST",
    ...jsonBody({ shopkeeper_id: shopkeeperId, customer_id: customerId, tone, language }),
  });
  // -> { customer, phone, amount_due, days_overdue, reminder_text, ... }
}