import { useState } from "react";
import MicButton from "../components/MicButton.jsx";
import ConfirmationCard from "../components/ConfirmationCard.jsx";
import Toast from "../components/Toast.jsx";
import { processTransaction } from "../services/api";

// TODO: replace with a real logged-in shopkeeper once auth exists.
// For now, grab an existing row's id from the "shopkeepers" table in
// Supabase (Table Editor), or insert one manually, and paste it here.
const DEMO_SHOPKEEPER_ID = "PASTE-A-REAL-SHOPKEEPER-UUID-HERE";

export default function Home() {
  const [transcript, setTranscript] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const [toastMsg, setToastMsg] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleConfirm() {
    setSaving(true);
    try {
      const result = await processTransaction(transcript, "hi", DEMO_SHOPKEEPER_ID);
      setToastMsg(
        `Saved: ₹${result.transaction.amount} for ${result.customer.name}`
      );
      setTranscript("");
      setAssistantReply("");
    } catch (err) {
      setToastMsg("Could not save: " + err.message);
    } finally {
      setSaving(false);
      setTimeout(() => setToastMsg(""), 3000);
    }
  }

  function handleCancel() {
    setTranscript("");
    setAssistantReply("");
  }

  return (
    <div className="page">
      <Toast message={toastMsg} />

      <div className="hero">
        <div className="hero-eyebrow">VOICE-FIRST KHATA</div>
        <h1 className="hero-heading">Speak it. We'll keep track.</h1>
        <p className="hero-subtext">Record a transaction in Hindi or English.</p>
        {!transcript && (
          <p className="hero-hint">
            Example: "Ramesh ne 500 rupaye ka udhaar liya"
          </p>
        )}

        {assistantReply && <p className="hero-hint">{assistantReply}</p>}

        <ConfirmationCard
          text={transcript}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      </div>

      <MicButton
        onTranscript={setTranscript}
        onAssistantReply={setAssistantReply}
      />
    </div>
  );
}