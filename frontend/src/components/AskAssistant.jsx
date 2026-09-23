import { useEffect, useRef, useState } from "react";
import { VoiceLiveClient } from "../services/voiceLive";
import { WS_BASE } from "../services/api";

const TOOL_LABELS = {
  get_customer_ledger: (args) => `${args?.customer_name || "Customer"} ka ledger check kar raha hoon...`,
  check_risk: (args) => `${args?.customer_name || "Customer"} ka risk check kar raha hoon...`,
  generate_reminder: (args) => `${args?.customer_name || "Customer"} ke liye reminder likh raha hoon...`,
  search_transactions: () => "Sab customers ka hisaab dekh raha hoon...",
  save_transaction: (args) => `${args?.customer_name || "Entry"} save kar raha hoon...`,
};

/**
 * The ASK flow: a live voice call, not a form. Opens full-screen, connects
 * to Voice Live over /ws/voice, and shows the conversation as chat bubbles
 * while the mic stays open — mirrors the reference app's call UI.
 */
export default function AskAssistant({ onClose, shopkeeperId }) {
  const [messages, setMessages] = useState([]); // { role: 'user' | 'assistant', text }
  // connecting -> connected -> ready -> (disconnected | error)
  const [status, setStatus] = useState("connecting");
  const [errorMsg, setErrorMsg] = useState(null);
  const [toolActivity, setToolActivity] = useState(null);
  // bumped to force the connection effect to run again for "Try again"
  const [attempt, setAttempt] = useState(0);
  const clientRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    setStatus("connecting");
    setErrorMsg(null);

    // shopkeeper_id must travel with the WebSocket connection itself (there's
    // no per-message auth on this socket), so it goes as a query param — the
    // backend reads it in voice_ws() and threads it through every MCP tool
    // call. Without this, get_customer_ledger/check_risk/etc. all fail with
    // "No shopkeeper session" and the assistant apologizes instead of
    // answering (see backend/app/routers/voice_live.py).
    const client = new VoiceLiveClient({
      wsUrl: `${WS_BASE}/ws/voice?shopkeeper_id=${encodeURIComponent(shopkeeperId || "")}`,
      onStatusChange: setStatus,
      onTranscript: (text) => {
        if (!text?.trim()) return;
        setMessages((prev) => [...prev, { role: "user", text }]);
      },
      onAssistantText: (text) => {
        if (!text?.trim()) return;
        setToolActivity(null);
        setMessages((prev) => [...prev, { role: "assistant", text }]);
      },
      onToolActivity: (evt) => {
        if (evt.type === "tool_call") {
          const label = TOOL_LABELS[evt.name]?.(evt.arguments) || "Checking...";
          setToolActivity(label);
        } else {
          setToolActivity(null);
        }
      },
      onError: (msg) => {
        setStatus("error");
        setErrorMsg(msg);
      },
    });

    clientRef.current = client;
    client.start();

    return () => {
      clientRef.current?.stop();
      clientRef.current = null;
    };
  }, [attempt, shopkeeperId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, toolActivity, errorMsg]);

  function endCall() {
    clientRef.current?.stop();
    onClose?.();
  }

  function retryCall() {
    setMessages([]);
    setToolActivity(null);
    setErrorMsg(null);
    setAttempt((n) => n + 1);
  }

  return (
    <div className="ask-sheet">
      <button className="ask-close-btn" onClick={endCall} aria-label="Close">
        ✕
      </button>
      <div className="ask-sheet-handle"></div>

      <div className="ask-transcript" ref={scrollRef}>
        {messages.length === 0 && (status === "connecting" || status === "connected") && (
          <p className="ask-hint">Connecting...</p>
        )}
        {messages.length === 0 && status === "ready" && (
          <p className="ask-hint">Kuch bhi pucho — jaise "Utkarsh ka kitna hisaab baaki hai?"</p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`ask-bubble ask-bubble-${m.role}`}>
            {m.text}
          </div>
        ))}

        {toolActivity && <div className="ask-tool-activity">{toolActivity}</div>}

        {status === "error" && (
          <div className="ask-error-banner">
            <p>⚠️ {errorMsg || "Something went wrong with the call."}</p>
            <button className="btn btn-secondary" onClick={retryCall}>
              Try again
            </button>
          </div>
        )}
      </div>

      <div className="ask-call-controls">
        <div className={`ask-mic-indicator ${status === "ready" ? "live" : ""}`} aria-hidden="true">
          <MicIcon />
        </div>
        <button className="ask-end-btn" onClick={endCall}>
          <PhoneOffIcon />
          End
        </button>
      </div>
    </div>
  );
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
      <path d="M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Z" fill="currentColor" />
      <path
        d="M19 11a1 1 0 0 0-2 0 5 5 0 0 1-10 0 1 1 0 0 0-2 0 7 7 0 0 0 6 6.93V21a1 1 0 0 0 2 0v-3.07A7 7 0 0 0 19 11Z"
        fill="currentColor"
      />
    </svg>
  );
}

function PhoneOffIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45 12.7 12.7 0 0 0 3.53.56 2 2 0 0 1 2 2V20a2 2 0 0 1-2 2A18 18 0 0 1 2 4a2 2 0 0 1 2-2h3.25a2 2 0 0 1 2 2 12.7 12.7 0 0 0 .56 3.53 2 2 0 0 1-.45 2.11L8.09 10.9" />
      <line x1="23" y1="1" x2="1" y2="23" />
    </svg>
  );
}