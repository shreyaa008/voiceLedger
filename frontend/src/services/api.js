// frontend/src/services/api.js
import { supabase } from "./supabaseClient";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export default API_BASE;

// Same host as API_BASE, just ws(s):// instead of http(s):// — used by the
// Ask call UI to reach /ws/voice.
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Distinguishes *why* a request failed so the UI can react correctly:
//   "network"    - fetch() itself threw: backend unreachable, offline,
//                   DNS/CORS failure. Not a validation problem — the
//                   request never even reached the server.
//   "auth"       - HTTP 401: no/expired Supabase session.
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

// Every authenticated call needs the current Supabase Auth access token —
// this is the ONLY thing that proves to the backend who's asking. The
// backend never trusts a shopkeeper_id the frontend sends; it always
// re-derives it from this token (see backend/app/services/auth.py).
async function authHeader() {
  const { data, error } = await supabase.auth.getSession();
  if (error || !data?.session?.access_token) {
    throw new ApiError("You're not signed in. Please log in again.", "auth", 401);
  }
  return { Authorization: `Bearer ${data.session.access_token}` };
}

async function apiFetch(path, options = {}, { auth = true } = {}) {
  const headers = { ...(options.headers || {}) };
  if (auth) {
    Object.assign(headers, await authHeader());
  }

  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
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
    const kind =
      res.status === 401
        ? "auth"
        : res.status === 400
        ? "validation"
        : res.status === 404
        ? "not_found"
        : "server";
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
  return apiFetch("/transcribe", { method: "POST", body: formData }, { auth: false });
  // -> { success, filename, text, language }
}

// Undo a just-saved transaction. Ownership is enforced server-side — this
// can only ever undo the signed-in shopkeeper's own transaction.
export async function deleteTransaction(transactionId) {
  return apiFetch(`/transactions/${transactionId}`, { method: "DELETE" });
}

// Edit a past entry's amount and/or type. Ownership is enforced server-side.
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
  }, { auth: false });
  // -> { success, customer, amount, type, date, language }
}

// Actually extracts AND saves — call this only after the shopkeeper confirms
// (or, for the auto-save entry flow, when extraction confidence is high).
// shopkeeper_id is derived server-side from the signed-in session, never
// sent by the client.
export async function processTransaction(text, language) {
  return apiFetch("/process-transaction", {
    method: "POST",
    ...jsonBody({ text, language }),
  });
  // -> { success, customer_created, customer, transaction }
}

// ---------- Ledger & Risk screens ----------

// Every customer with balance + risk, plus "You'll Get / You'll Give"
// totals — scoped to the signed-in shopkeeper by the backend.
export async function getDashboardSummary() {
  return apiFetch("/dashboard/summary");
  // -> { totals, risk_counts, customers: [...] }
}

// All entries (udhaar + payments) for one customer. The backend checks
// the customer belongs to the signed-in shopkeeper before returning
// anything.
export async function getCustomerLedger(customerId) {
  return apiFetch(`/customers/${encodeURIComponent(customerId)}/ledger`);
  // -> { customer_id, transactions: [...] }
}

// ---------- Shopkeeper identity (Supabase Auth) ----------

// Get-or-create the shopkeeper row linked to the signed-in Supabase Auth
// user. Call once right after sign up (or first login on a fresh
// account) — see ShopkeeperContext.jsx.
export async function bootstrapShopkeeper(name, phone, preferredLanguage = "hi") {
  return apiFetch("/shopkeepers/bootstrap", {
    method: "POST",
    ...jsonBody({ name, phone: phone || null, preferred_language: preferredLanguage }),
  });
  // -> { shopkeeper: { id, name, phone, preferred_language } }
}

// The signed-in user's shopkeeper profile, or throws a "not_found" ApiError
// (404) if bootstrap hasn't run yet for this account.
export async function getMyShopkeeper() {
  return apiFetch("/shopkeepers/me");
  // -> { shopkeeper: { id, name, phone, preferred_language } }
}

// Ready-to-send payment reminder text. shopkeeper_id is derived
// server-side from the signed-in session.
export async function generateReminder(customerId, tone, language) {
  return apiFetch("/dashboard/reminder", {
    method: "POST",
    ...jsonBody({ customer_id: customerId, tone, language }),
  });
  // -> { customer, phone, amount_due, days_overdue, reminder_text, ... }
}