import { useState } from "react";
import AskAssistant from "../components/AskAssistant.jsx";
import { DEMO_SHOPKEEPER_ID } from "../config";

export default function Ask() {
  const [callActive, setCallActive] = useState(false);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Ask VoiceLedger</h2>
        <p className="page-subtitle">Ask a question about any customer, by voice.</p>
      </div>

      <div className="ask-launcher">
        <p className="hero-hint">"Utkarsh ka kitna hisaab baaki hai?" · "Suresh ka risk kaisa hai?"</p>
        <button className="btn btn-primary ask-launch-btn" onClick={() => setCallActive(true)}>
          <CallIcon /> Start a voice call
        </button>
      </div>

      {callActive && (
        <AskAssistant shopkeeperId={DEMO_SHOPKEEPER_ID} onClose={() => setCallActive(false)} />
      )}
    </div>
  );
}

function CallIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  );
}