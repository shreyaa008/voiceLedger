import { useState, useCallback } from "react";
import EntryRecorder from "../components/EntryRecorder.jsx";
import Toast from "../components/Toast.jsx";
import { deleteTransaction } from "../services/api";

// TODO: replace with a real logged-in shopkeeper once auth exists.
// For now, grab an existing row's id from the "shopkeepers" table in
// Supabase (Table Editor), or insert one manually, and paste it here.
const DEMO_SHOPKEEPER_ID = "178a88bd-46ed-45fb-b8a8-2a3949cee6c4";

export default function Home() {
  const [sessionLog, setSessionLog] = useState([]);
  const [toast, setToast] = useState(null); // { message, actionLabel, onAction }

  const showToast = useCallback((message, actionLabel, onAction) => {
    setToast({ message, actionLabel, onAction });
    window.clearTimeout(showToast._t);
    showToast._t = window.setTimeout(() => setToast(null), 5000);
  }, []);

  const handleSaved = useCallback(
    (entry) => {
      setSessionLog((prev) => [entry, ...prev]);

      const verb = entry.type === "credit" ? "credit for" : "payment from";
      showToast(`Saved ₹${entry.amount} ${verb} ${entry.customer}`, "UNDO", async () => {
        try {
          await deleteTransaction(entry.id);
          setSessionLog((prev) => prev.filter((e) => e.id !== entry.id));
          showToast("Removed.");
        } catch (err) {
          showToast("Could not undo: " + err.message);
        }
      });
    },
    [showToast]
  );

  const handleMissed = useCallback(
    (text) => {
      showToast(`Heard "${text}" — couldn't catch the customer/amount. Try again.`);
    },
    [showToast]
  );

  const handleError = useCallback(
    (msg) => {
      showToast(msg);
    },
    [showToast]
  );

  return (
    <div className="page">
      <Toast message={toast?.message} actionLabel={toast?.actionLabel} onAction={toast?.onAction} />

      <div className="hero">
        <div className="hero-eyebrow">VOICE-FIRST KHATA</div>
        <h1 className="hero-heading">Speak it. We'll keep track.</h1>
        <p className="hero-subtext">Record a transaction in Hindi or English.</p>
        {sessionLog.length === 0 && (
          <p className="hero-hint">Example: "Ramesh ne 500 rupaye ka udhaar liya"</p>
        )}

        {sessionLog.length > 0 && (
          <div className="entry-log">
            <div className="entry-log-title">Added this session</div>
            {sessionLog.map((entry) => (
              <div className="entry-log-row" key={entry.id}>
                <span className="entry-log-customer">{entry.customer}</span>
                <span className={`badge badge-${entry.type}`}>
                  {entry.type === "credit" ? "Udhaar" : "Payment"}
                </span>
                <span className="entry-log-amount">₹{entry.amount}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <EntryRecorder
        shopkeeperId={DEMO_SHOPKEEPER_ID}
        onSaved={handleSaved}
        onMissed={handleMissed}
        onError={handleError}
      />
    </div>
  );
}