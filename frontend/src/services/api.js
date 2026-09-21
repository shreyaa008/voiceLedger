// frontend/src/services/api.js
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export default API_BASE;

// Same host as API_BASE, just ws(s):// instead of http(s):// — used by the
// Ask call UI to reach /ws/voice.
export const WS_BASE = API_BASE.replace(/^http/, "ws");

// Send a recorded utterance (WAV blob) to Azure AI Speech for transcription.
export async function transcribeAudio(blob) {
  const formData = new FormData();
  formData.append("file", blob, "entry.wav");

  const res = await fetch(`${API_BASE}/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Transcription failed");
  }

  return res.json(); // { success, filename, text, language }
}

// Undo a just-saved transaction.
export async function deleteTransaction(transactionId) {
  const res = await fetch(`${API_BASE}/transactions/${transactionId}`, {
    method: "DELETE",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not undo transaction");
  }

  return res.json();
}

// Extract customer/amount/type/date from raw text — DISPLAY ONLY, saves nothing.
export async function extractTransaction(text, language = "hi") {
  const res = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Extraction failed");
  }

  return res.json(); // { success, customer, amount, type, date, language }
}

// Actually extracts AND saves — call this only after the shopkeeper confirms.
export async function processTransaction(text, language, shopkeeperId) {
  const res = await fetch(`${API_BASE}/process-transaction`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, language, shopkeeper_id: shopkeeperId }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not save transaction");
  }

  return res.json(); // { success, customer_created, customer, transaction }
}

// ---------- Ledger & Risk screens ----------

// Every customer with balance + risk, plus "You'll Get / You'll Give" totals.
export async function getDashboardSummary(shopkeeperId) {
  const res = await fetch(
    `${API_BASE}/dashboard/summary?shopkeeper_id=${encodeURIComponent(shopkeeperId)}`
  );

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not load your ledger");
  }

  return res.json(); // { totals, risk_counts, customers: [...] }
}

// All entries (udhaar + payments) for one customer.
export async function getCustomerLedger(customerId) {
  const res = await fetch(`${API_BASE}/customers/${encodeURIComponent(customerId)}/ledger`);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not load this customer's entries");
  }

  return res.json(); // { customer_id, transactions: [...] }
}

// Ready-to-send payment reminder text.
export async function generateReminder(shopkeeperId, customerId, tone, language) {
  const res = await fetch(`${API_BASE}/dashboard/reminder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      shopkeeper_id: shopkeeperId,
      customer_id: customerId,
      tone,
      language,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Could not create the reminder");
  }

  return res.json(); // { customer, phone, amount_due, days_overdue, reminder_text, ... }
}