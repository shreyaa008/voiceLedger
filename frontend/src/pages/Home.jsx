import { useState } from "react";
import MicButton from "../components/MicButton.jsx";
import ConfirmationCard from "../components/ConfirmationCard.jsx";

export default function Home() {
  const [transcript, setTranscript] = useState("");

  function handleConfirm() {
    alert("Saved (placeholder): " + transcript);
    setTranscript("");
  }

  function handleCancel() {
    setTranscript("");
  }

  return (
    <div>
      <h2>Record a Transaction</h2>
      <MicButton onRecordingComplete={setTranscript} />
      <ConfirmationCard
        text={transcript}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </div>
  );
}