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
export default function AskAssistant({ onClose }) {
  const [messages, setMessages] = useState([]); // { role: 'user' | 'assistant', text }
  const [status, setStatus] = useState("connecting"); // connecting | connected | disconnected | error
  const [toolActivity, setToolActivity] = useState(null);
  const clientRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    const client = new VoiceLiveClient({
      wsUrl: `${WS_BASE}/ws/voice`,
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
        setMessages((prev) => [...prev, { role: "assistant", text: `⚠️ ${msg}` }]);
      },
    });

    clientRef.current = client;
    client.start();

    return () => {
      clientRef.current?.stop();
      clientRef.current = null;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, toolActivity]);

  function endCall() {
    clientRef.current?.stop();
    onClose?.();
  }

  return (
    <div className="ask-sheet">
      <button className="ask-close-btn" onClick={endCall} aria-label="Close">
        ✕
      </button>
      <div className="ask-sheet-handle"></div>

      <div className="ask-transcript" ref={scrollRef}>
        {messages.length === 0 && status === "connecting" && (
          <p className="ask-hint">Connecting...</p>
        )}
        {messages.length === 0 && status === "connected" && (
          <p className="ask-hint">Kuch bhi pucho — jaise "Utkarsh ka kitna hisaab baaki hai?"</p>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`ask-bubble ask-bubble-${m.role}`}>
            {m.text}
          </div>
        ))}

        {toolActivity && <div className="ask-tool-activity">{toolActivity}</div>}
      </div>

      <div className="ask-call-controls">
        <div className={`ask-mic-indicator ${status === "connected" ? "live" : ""}`} aria-hidden="true">
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