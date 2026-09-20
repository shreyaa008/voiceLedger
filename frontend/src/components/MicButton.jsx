import { useState } from "react";

export default function MicButton({ onRecordingComplete }) {
  const [isRecording, setIsRecording] = useState(false);

  function startRecording() {
    setIsRecording(true);
  }

  function stopAndConfirm() {
    setIsRecording(false);
    onRecordingComplete("Ramesh ne 500 rupaye ka udhaar liya");
  }

  function cancelRecording() {
    setIsRecording(false);
  }

  return (
    <>
      {isRecording && <div className="mic-overlay" onClick={cancelRecording} />}

      <div className="mic-dock">
        {!isRecording && <div className="mic-tooltip">Tap to speak</div>}

        {isRecording ? (
          <div className="mic-recording-stack">
            <span className="mic-state-label">Listening...</span>
            <div className="mic-actions">
              <div className="mic-fab-wrap">
                <button
                  className="mic-fab recording"
                  onClick={stopAndConfirm}
                  aria-label="Tap to finish"
                >
                  <div className="mic-waveform">
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                  </div>
                </button>
              </div>
              <button className="mic-cancel" onClick={cancelRecording} aria-label="Cancel">✕</button>
            </div>
            <span className="mic-tooltip">Tap to finish</span>
          </div>
        ) : (
          <div className="mic-fab-wrap">
            <span className="mic-ring r2"></span>
            <span className="mic-ring r1"></span>
            <button className="mic-fab" onClick={startRecording} aria-label="Tap to speak">
              <MicIcon />
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function MicIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z"
        fill="currentColor"
      />
      <path
        d="M19 11a1 1 0 0 0-2 0 5 5 0 0 1-10 0 1 1 0 0 0-2 0 7 7 0 0 0 6 6.93V21a1 1 0 0 0 2 0v-3.07A7 7 0 0 0 19 11Z"
        fill="currentColor"
      />
    </svg>
  );
}