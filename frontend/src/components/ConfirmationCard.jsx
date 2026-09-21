import { useEffect, useState } from "react";
import { extractTransaction } from "../services/api";

export default function ConfirmationCard({ text, language = "hi", onConfirm, onCancel }) {
  const [extracted, setExtracted] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!text) {
      setExtracted(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    extractTransaction(text, language)
      .then((data) => {
        if (!cancelled) setExtracted(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [text, language]);

  if (!text) return null;

  return (
    <div className="confirmation-card">
      <h3>Let's make sure</h3>

      {loading && <p className="confirmation-loading">Reading transaction details...</p>}

      {error && <p className="confirmation-error">Could not extract details: {error}</p>}

      {!loading && extracted && (
        <>
          <div className="confirmation-row">
            <span className="confirmation-label">Customer</span>
            <span className="confirmation-value">{extracted.customer || "Unknown"}</span>
          </div>
          <div className="confirmation-row">
            <span className="confirmation-label">Amount</span>
            <span className="confirmation-amount">
              {extracted.amount != null ? `₹${extracted.amount}` : "—"}
            </span>
          </div>
          <div className="confirmation-row">
            <span className="confirmation-label">Type</span>
            <span className="badge">
              {extracted.type === "credit" ? "Udhaar (Credit)" : "Payment"}
            </span>
          </div>
        </>
      )}

      <p className="confirmation-quote">"{text}"</p>

      <div className="confirmation-actions">
        <button
          className="btn btn-primary"
          onClick={onConfirm}
          disabled={loading || !extracted}
        >
          Confirm Transaction
        </button>
        <button className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
