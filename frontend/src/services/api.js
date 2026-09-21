// TODO: functions that call our FastAPI backend, e.g.:
// export async function transcribeAudio(blob) { ... }
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";
export default API_BASE;

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