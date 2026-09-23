// frontend/src/services/voiceLive.js
//
// Handles the full browser-side Voice Live pipeline:
//   1. Capture microphone audio
//   2. Convert it to 16-bit PCM at 24kHz (what Azure Voice Live expects)
//   3. Stream it over a WebSocket to the FastAPI backend (/ws/voice)
//   4. Receive audio replies + transcripts back, and play the audio
//
// Status values reported via onStatusChange, in order:
//   "connecting"  - WebSocket is being opened
//   "connected"   - socket open, mic is starting
//   "ready"       - backend confirmed the Voice Live session is configured;
//                    it is now safe to talk and audio will be sent
//   "error"       - something failed; onError carries a human-readable reason
//   "disconnected"- socket closed (either we called stop(), or it dropped)

const TARGET_SAMPLE_RATE = 24000;
const CONNECT_TIMEOUT_MS = 8000; // WebSocket must open within this long
const READY_TIMEOUT_MS = 12000; // backend must send {type:"ready"} within this long (mirrors the backend's own watchdog, with slack for network latency)

export class VoiceLiveClient {
  constructor({ wsUrl, onTranscript, onAssistantText, onError, onStatusChange, onToolActivity }) {
    this.wsUrl = wsUrl;
    this.onTranscript = onTranscript;
    this.onAssistantText = onAssistantText;
    this.onError = onError;
    this.onStatusChange = onStatusChange;
    // Fired when the backend calls one of the MCP tools (get_customer_ledger,
    // check_risk, ...) to ground its answer — lets the call UI show something
    // like "checking Utkarsh's ledger..." instead of a silent pause.
    // Payload: { type: "tool_call" | "tool_result", name, arguments?, data? }
    this.onToolActivity = onToolActivity;

    this.ws = null;
    this.sessionReady = false;
    this.stopped = false; // true once stop() has been called, so late/async
    // events from a closing socket or a dying AudioContext never reach the
    // UI as a spurious error after the person already ended the call.
    this.errored = false; // true once onError has fired, so the close that
    // inevitably follows (we always close the socket after an error)
    // doesn't overwrite the "error" status back to "disconnected" and wipe
    // out the error banner/retry button the person is looking at.

    this.connectTimer = null;
    this.readyTimer = null;

    // mic capture
    this.micContext = null;
    this.micSource = null;
    this.processor = null;
    this.muteGain = null;
    this.stream = null;

    // playback
    this.playbackContext = null;
    this.playbackQueueTime = 0;
  }

  _reportError(msg) {
    this.errored = true;
    this.onError?.(msg);
  }

  async start() {
    this.stopped = false;

    // Create (and try to resume) the playback AudioContext up front, in the
    // same call stack as the user's "Start a voice call" click, instead of
    // lazily on the first inbound audio chunk. A context created inside a
    // WebSocket message handler has no user-gesture "transient activation"
    // behind it, so browsers can leave it permanently suspended — audio
    // gets queued into it but never actually plays. That's the main reason
    // responses were sometimes silent. Creating + resuming it now, while
    // we're still inside the click's activation window, avoids that.
    try {
      this.playbackContext = new (window.AudioContext || window.webkitAudioContext)();
      this.playbackQueueTime = this.playbackContext.currentTime;
      if (this.playbackContext.state === "suspended") {
        await this.playbackContext.resume().catch(() => {});
      }
    } catch (err) {
      console.error("Could not create playback audio context:", err);
      // Not fatal by itself — we still try the call, but flag it so the
      // person understands why they might not hear anything.
      this.onError?.("Could not initialize audio playback in this browser.");
      this.errored = false; // recoverable — don't suppress a later real error
    }

    this.ws = new WebSocket(this.wsUrl);
    this.ws.binaryType = "arraybuffer";

    this.connectTimer = setTimeout(() => {
      if (this.ws?.readyState === WebSocket.CONNECTING) {
        this._reportError("Could not reach the server. Check your connection and that the backend is running.");
        this._hardStop("connect-timeout");
      }
    }, CONNECT_TIMEOUT_MS);

    this.ws.onopen = () => {
      clearTimeout(this.connectTimer);
      this.onStatusChange?.("connected");

      // Once the session is configured Azure-side, the backend must tell us
      // — if it never does (Azure unreachable, bad credentials that only
      // fail after connecting, etc.) don't leave the call UI stuck forever.
      this.readyTimer = setTimeout(() => {
        if (!this.sessionReady && !this.stopped) {
          this._reportError("Voice Live didn't respond in time. Please try again.");
          this._hardStop("ready-timeout");
        }
      }, READY_TIMEOUT_MS);

      this._startMic().catch((err) => {
        console.error("Mic error:", err);
        this._reportError("Could not access microphone: " + err.message);
        // Without a mic there's nothing useful this call can do — end it
        // cleanly instead of leaving a connected-but-mute socket open,
        // which is exactly what made "Start Voice Call" look like it did
        // nothing.
        this._hardStop("mic-failed");
      });
    };

    this.ws.onmessage = (event) => {
      if (this.stopped) return;
      if (typeof event.data === "string") {
        this._handleJson(event.data);
      } else {
        this._playAudioChunk(event.data);
      }
    };

    this.ws.onerror = () => {
      if (this.stopped) return;
      // The browser gives us no detail on WebSocket error events; the
      // close event that immediately follows carries the actual reason
      // (see onclose below), so we only use this as a fallback signal.
      this._reportError("WebSocket connection error");
    };

    this.ws.onclose = (event) => {
      clearTimeout(this.connectTimer);
      clearTimeout(this.readyTimer);
      const wasStopped = this.stopped;
      const alreadyErrored = this.errored;
      this._stopMic();
      this._stopPlayback();

      // A clean, user-initiated close (code 1000, or stop() already ran)
      // needs no explanation. Anything else — the backend rejecting us,
      // Azure dropping, a network blip — should be visible instead of
      // just silently going quiet.
      if (!wasStopped && !alreadyErrored && event.code !== 1000) {
        this._reportError(
          event.reason || `Connection closed unexpectedly (code ${event.code}).`
        );
      }

      // Don't downgrade an "error" status the UI is already showing (with
      // its retry button) back to a plain "disconnected" — the close that
      // follows almost every error is expected, not new information.
      if (!this.errored) {
        this.onStatusChange?.("disconnected");
      }
    };
  }

  stop() {
    this._hardStop("user-ended");
  }

  _hardStop(_reason) {
    this.stopped = true;
    clearTimeout(this.connectTimer);
    clearTimeout(this.readyTimer);
    try {
      this.ws?.close(1000, "client stopped");
    } catch {
      // ignore — socket may already be closed/closing
    }
    this._stopMic();
    this._stopPlayback();
  }

  _handleJson(raw) {
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      return;
    }

    if (payload.type === "ready") {
      clearTimeout(this.readyTimer);
      this.sessionReady = true;
      this.onStatusChange?.("ready");
    } else if (payload.type === "transcript") {
      this.onTranscript?.(payload.text);
    } else if (payload.type === "assistant_text") {
      this.onAssistantText?.(payload.text);
    } else if (payload.type === "tool_call" || payload.type === "tool_result") {
      this.onToolActivity?.(payload);
    } else if (payload.type === "error") {
      this._reportError(payload.message);
    }
  }

  async _startMic() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (this.stopped) {
      // stop() was called while the permission prompt was open — tear the
      // stream back down instead of wiring it up.
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
      return;
    }

    this.micContext = new (window.AudioContext || window.webkitAudioContext)();
    if (this.micContext.state === "suspended") {
      await this.micContext.resume().catch(() => {});
    }
    this.micSource = this.micContext.createMediaStreamSource(this.stream);

    // ScriptProcessorNode is deprecated but still universally supported and
    // far simpler to wire up than AudioWorklet for a student project deadline.
    const bufferSize = 4096;
    this.processor = this.micContext.createScriptProcessor(bufferSize, 1, 1);

    const inputSampleRate = this.micContext.sampleRate; // usually 48000

    this.processor.onaudioprocess = (e) => {
      if (this.ws?.readyState !== WebSocket.OPEN) return;
      // Don't stream audio to Azure until the backend has confirmed the
      // session is configured (voice/instructions/VAD/tools). Sending
      // earlier meant Azure could process the first moments of speech
      // under stale/default config — a real cause of calls that seemed to
      // "do nothing" or reply in the wrong language.
      if (!this.sessionReady) return;

      const input = e.inputBuffer.getChannelData(0);
      const resampled = downsample(input, inputSampleRate, TARGET_SAMPLE_RATE);
      const pcm16 = floatTo16BitPCM(resampled);
      this.ws.send(pcm16.buffer);
    };

    this.micSource.connect(this.processor);

    // IMPORTANT: ScriptProcessorNode only fires onaudioprocess if connected
    // to a destination — but we do NOT want to hear our own raw mic audio
    // played back (that would cause an instant feedback echo). Route it
    // through a silent gain node instead of straight to speakers.
    this.muteGain = this.micContext.createGain();
    this.muteGain.gain.value = 0;
    this.processor.connect(this.muteGain);
    this.muteGain.connect(this.micContext.destination);
  }

  _stopMic() {
    this.processor?.disconnect();
    this.micSource?.disconnect();
    this.muteGain?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.micContext?.close().catch(() => {});

    this.processor = null;
    this.micSource = null;
    this.muteGain = null;
    this.stream = null;
    this.micContext = null;
  }

  _stopPlayback() {
    // Previously the playback AudioContext was never closed, so every call
    // left one behind. Browsers cap the number of live AudioContexts, so a
    // few calls in the same session could start silently failing to play
    // anything at all.
    this.playbackContext?.close().catch(() => {});
    this.playbackContext = null;
    this.playbackQueueTime = 0;
  }

  _playAudioChunk(arrayBuffer) {
    if (!this.playbackContext) return; // torn down (call ended) or failed to init

    if (this.playbackContext.state === "suspended") {
      // Best-effort re-resume — some browsers suspend a context again after
      // periods of silence.
      this.playbackContext.resume().catch(() => {});
    }

    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const audioBuffer = this.playbackContext.createBuffer(1, float32.length, TARGET_SAMPLE_RATE);
    audioBuffer.copyToChannel(float32, 0);

    const src = this.playbackContext.createBufferSource();
    src.buffer = audioBuffer;
    src.connect(this.playbackContext.destination);

    // queue chunks back-to-back instead of overlapping them
    const startAt = Math.max(this.playbackQueueTime, this.playbackContext.currentTime);
    src.start(startAt);
    this.playbackQueueTime = startAt + audioBuffer.duration;
  }
}

function downsample(buffer, inputRate, outputRate) {
  if (outputRate === inputRate) return buffer;
  const ratio = inputRate / outputRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    result[i] = buffer[Math.floor(i * ratio)];
  }
  return result;
}

function floatTo16BitPCM(float32Array) {
  const out = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return out;
}