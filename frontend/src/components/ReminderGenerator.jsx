import { useEffect, useState } from "react";
import { generateReminder } from "../services/api";
import { DEMO_SHOPKEEPER_ID } from "../config";
import { formatINR } from "../utils/format";
import Spinner from "./Spinner.jsx";

const TONES = [
  { id: "polite", label: "Polite" },
  { id: "standard", label: "Standard" },
  { id: "firm", label: "Firm" },
];
const LANGS = [
  { id: "hi", label: "Hindi" },
  { id: "en", label: "English" },
];

// wa.me needs the number with country code and no symbols.
function whatsappLink(phone, text) {
  const digits = String(phone || "").replace(/\D/g, "");
  const full = digits.length === 10 ? `91${digits}` : digits;
  const base = full ? `https://wa.me/${full}` : "https://wa.me/";
  return `${base}?text=${encodeURIComponent(text)}`;
}

// Pop-up: choose tone + language, get a message, copy it or open WhatsApp.
export default function ReminderGenerator({ customer, onClose }) {
  const [tone, setTone] = useState("polite");
  const [language, setLanguage] = useState("hi");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  // Make a fresh message whenever tone or language changes.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setCopied(false);

    generateReminder(DEMO_SHOPKEEPER_ID, customer.id, tone, language)
      .then((res) => {
        if (!cancelled) setText(res.reminder_text);
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
  }, [customer.id, tone, language]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy — select the text and copy it by hand.");
    }
  };

  return (
    <div className="modal-backdrop modal-top" onClick={onClose}>
      <div className="modal-card" role="dialog" aria-label="Payment reminder" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Remind {customer.name}</h3>
            <p className="modal-sub">They owe {formatINR(customer.balance)}</p>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <div className="chip-row">
          <span className="chip-label">Tone</span>
          {TONES.map((t) => (
            <button
              key={t.id}
              className={`chip ${tone === t.id ? "chip-active" : ""}`}
              onClick={() => setTone(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="chip-row">
          <span className="chip-label">Language</span>
          {LANGS.map((l) => (
            <button
              key={l.id}
              className={`chip ${language === l.id ? "chip-active" : ""}`}
              onClick={() => setLanguage(l.id)}
            >
              {l.label}
            </button>
          ))}
        </div>

        <div className="reminder-box">
          {loading ? (
            <div className="reminder-loading">
              <Spinner /> Writing message…
            </div>
          ) : (
            <textarea
              className="reminder-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              aria-label="Reminder message"
            />
          )}
        </div>

        {error && <p className="inline-error">{error}</p>}

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={copy} disabled={loading || !text}>
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <a
            className={`btn btn-primary btn-link ${loading || !text ? "btn-disabled" : ""}`}
            href={loading || !text ? undefined : whatsappLink(customer.phone, text)}
            target="_blank"
            rel="noreferrer"
          >
            Send on WhatsApp
          </a>
        </div>
        {!customer.phone && (
          <p className="modal-note">No phone number saved — WhatsApp will let you pick the contact.</p>
        )}
      </div>
    </div>
  );
}