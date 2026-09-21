// frontend/src/services/voiceLive.js
//
// Handles the full browser-side Voice Live pipeline:
//   1. Capture microphone audio
//   2. Convert it to 16-bit PCM at 24kHz (what Azure Voice Live expects)
//   3. Stream it over a WebSocket to the FastAPI backend (/ws/voice)
//   4. Receive audio replies + transcripts back, and play the audio

const TARGET_SAMPLE_RATE = 24000;

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

  async start() {
    this.ws = new WebSocket(this.wsUrl);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this.onStatusChange?.("connected");
      this._startMic().catch((err) => {
        console.error("Mic error:", err);
        this.onError?.("Could not access microphone: " + err.message);
      });
    };

    this.ws.onmessage = (event) => {
      if (typeof event.data === "string") {
        this._handleJson(event.data);
      } else {
        this._playAudioChunk(event.data);
      }
    };

    this.ws.onerror = () => {
      this.onError?.("WebSocket connection error");
    };

    this.ws.onclose = () => {
      this.onStatusChange?.("disconnected");
      this._stopMic();
    };
  }

  stop() {
    this.ws?.close();
    this._stopMic();
  }

  _handleJson(raw) {
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      return;
    }

    if (payload.type === "transcript") {
      this.onTranscript?.(payload.text);
    } else if (payload.type === "assistant_text") {
      this.onAssistantText?.(payload.text);
    } else if (payload.type === "tool_call" || payload.type === "tool_result") {
      this.onToolActivity?.(payload);
    } else if (payload.type === "error") {
      this.onError?.(payload.message);
    }
  }

  async _startMic() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    this.micContext = new (window.AudioContext || window.webkitAudioContext)();
    this.micSource = this.micContext.createMediaStreamSource(this.stream);

    // ScriptProcessorNode is deprecated but still universally supported and
    // far simpler to wire up than AudioWorklet for a student project deadline.
    const bufferSize = 4096;
    this.processor = this.micContext.createScriptProcessor(bufferSize, 1, 1);

    const inputSampleRate = this.micContext.sampleRate; // usually 48000

    this.processor.onaudioprocess = (e) => {
      if (this.ws?.readyState !== WebSocket.OPEN) return;

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
    this.micContext?.close();

    this.processor = null;
    this.micSource = null;
    this.muteGain = null;
    this.stream = null;
    this.micContext = null;
  }

  _playAudioChunk(arrayBuffer) {
    if (!this.playbackContext) {
      this.playbackContext = new (window.AudioContext || window.webkitAudioContext)();
      this.playbackQueueTime = this.playbackContext.currentTime;
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