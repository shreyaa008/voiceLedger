import { useState } from "react";
import MicButton from "../components/MicButton.jsx";
import ConfirmationCard from "../components/ConfirmationCard.jsx";
import Toast from "../components/Toast.jsx";

export default function Home() {
  const [transcript, setTranscript] = useState("");
  const [toastMsg, setToastMsg] = useState("");

  function handleConfirm() {
    setToastMsg("Saved: " + transcript);
    setTranscript("");
    setTimeout(() => setToastMsg(""), 2500);
  }

  function handleCancel() {
    setTranscript("");
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

        <ConfirmationCard
          text={transcript}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      </div>

      <MicButton onRecordingComplete={setTranscript} />
    </div>
  );
}