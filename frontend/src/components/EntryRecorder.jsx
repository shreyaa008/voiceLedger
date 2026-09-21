import { useCallback, useRef, useState } from "react";
import { SegmentedRecorder } from "../services/wavRecorder";
import { transcribeAudio, processTransaction } from "../services/api";

// Azure Speech returns BCP-47 codes like "en-US" / "hi-IN".
// The rest of the backend (extract_transaction, save) only knows "en" / "hi".
function toShortLang(bcp47) {
  return (bcp47 || "").toLowerCase().startsWith("hi") ? "hi" : "en";
}

/**
 * Mic control for recording transactions ("udhaar diya", "payment mila"...).
 * Uses plain Azure AI Speech batch transcription per utterance — NOT Voice
 * Live — then saves straight to the ledger. Stays open across multiple
 * back-to-back entries until the shopkeeper taps to stop.
 */
export default function EntryRecorder({ shopkeeperId, onSaved, onMissed, onError }) {
  const [sessionActive, setSessionActive] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | listening | hearing | saving
  const recorderRef = useRef(null);

  const handleSegment = useCallback(
    async (blob) => {
      setStatus("saving");
      try {
        const { text, language } = await transcribeAudio(blob);
        const shortLang = toShortLang(language);

        if (!text || !text.trim()) {
          setStatus(sessionActive ? "listening" : "idle");
          return;
        }

        try {
          const result = await processTransaction(text, shortLang, shopkeeperId);
          onSaved?.({
            id: result.transaction.id,
            customer: result.customer.name,
            amount: result.transaction.amount,
            type: result.transaction.type,
            heardText: text,
          });
        } catch (saveErr) {
          // Couldn't identify customer/amount/type from this utterance —
          // don't block the session, just surface it and keep listening.
          onMissed?.(text, saveErr.message);
        }
      } catch (err) {
        onError?.(err.message);
      } finally {
        setStatus((s) => (s === "saving" ? "listening" : s));
      }
    },
    [shopkeeperId, onSaved, onMissed, onError, sessionActive]
  );

  const startSession = useCallback(async () => {
    setSessionActive(true);
    setStatus("listening");

    const recorder = new SegmentedRecorder({
      onSegment: handleSegment,
      onSpeechStart: () => setStatus("hearing"),
      onSpeechEnd: () => setStatus("saving"),
      onError: (msg) => onError?.(msg),
    });

    recorderRef.current = recorder;

    try {
      await recorder.start();
    } catch (err) {
      onError?.("Could not access microphone: " + err.message);
      setSessionActive(false);
      setStatus("idle");
    }
  }, [handleSegment, onError]);

  const stopSession = useCallback(() => {
    recorderRef.current?.stop();
    recorderRef.current = null;
    setSessionActive(false);
    setStatus("idle");
  }, []);

  const statusLabel =
    status === "hearing" ? "Listening..." : status === "saving" ? "Saving..." : "Sun raha hoon...";

  return (
    <>
      {sessionActive && <div className="mic-overlay" onClick={stopSession} />}

      <div className="mic-dock">
        {!sessionActive && <div className="mic-tooltip">Tap to speak</div>}

        {sessionActive ? (
          <div className="mic-recording-stack">
            <span className="mic-state-label">{statusLabel}</span>

            <div className="mic-actions">
              <div className="mic-fab-wrap">
                <button className="mic-fab recording" onClick={stopSession} aria-label="Tap to finish">
                  <div className="mic-waveform">
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                    <span className="bar"></span>
                  </div>
                </button>
              </div>
              <button className="mic-cancel" onClick={stopSession} aria-label="Stop">
                ✕
              </button>
            </div>
            <span className="mic-tooltip">Speak entries one after another, tap ✕ when done</span>
          </div>
        ) : (
          <div className="mic-fab-wrap">
            <span className="mic-ring r2"></span>
            <span className="mic-ring r1"></span>
            <button className="mic-fab" onClick={startSession} aria-label="Tap to speak">
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
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" fill="currentColor" />
      <path
        d="M19 11a1 1 0 0 0-2 0 5 5 0 0 1-10 0 1 1 0 0 0-2 0 7 7 0 0 0 6 6.93V21a1 1 0 0 0 2 0v-3.07A7 7 0 0 0 19 11Z"
        fill="currentColor"
      />
    </svg>
  );
}