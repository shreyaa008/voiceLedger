import { useState } from "react";

export default function MicButton({ onRecordingComplete }) {
  const [isRecording, setIsRecording] = useState(false);

  function handleClick() {
    if (!isRecording) {
      // starting to record
      setIsRecording(true);
    } else {
      // stopping — for now, fake it with placeholder text
      setIsRecording(false);
      onRecordingComplete("Ramesh ne 500 rupaye ka udhaar liya");
    }
  }

  return (
    <button onClick={handleClick}>
      {isRecording ? "🔴 Stop Recording" : "🎤 Tap to Speak"}
    </button>
  );
}