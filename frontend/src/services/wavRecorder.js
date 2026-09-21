// frontend/src/services/wavRecorder.js
//
// Purpose-built for the ENTRY flow (not Ask/Voice Live).
// Azure AI Speech's batch recognizer wants a plain 16kHz/16-bit/mono WAV
// file, so instead of streaming to a conversational model we just record
// locally, cut it into utterances with a simple volume-based VAD, encode
// each one as WAV, and hand it back as a Blob for POST /transcribe.
//
// Kept deliberately simple (no AudioWorklet) to match the rest of this
// codebase's ScriptProcessorNode approach in voiceLive.js.

const TARGET_SAMPLE_RATE = 16000;
const SILENCE_RMS_THRESHOLD = 0.012; // below this = "quiet"
const SILENCE_HOLD_MS = 900; // how long it must stay quiet to end an utterance
const MIN_SPEECH_MS = 350; // ignore coughs/taps shorter than this
const MAX_SEGMENT_MS = 15000; // safety cap so one segment can't run forever

export class SegmentedRecorder {
  constructor({ onSegment, onLevel, onError, onSpeechStart, onSpeechEnd }) {
    this.onSegment = onSegment; // (blob) => void, called once per utterance
    this.onLevel = onLevel; // (rms 0..1) => void, optional, for UI animation
    this.onError = onError;
    this.onSpeechStart = onSpeechStart;
    this.onSpeechEnd = onSpeechEnd;

    this.audioContext = null;
    this.source = null;
    this.processor = null;
    this.muteGain = null;
    this.stream = null;

    this.speaking = false;
    this.speechStartedAt = 0;
    this.silenceStartedAt = null;
    this.chunks = [];
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    this.source = this.audioContext.createMediaStreamSource(this.stream);

    const bufferSize = 4096;
    this.processor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);

    this.processor.onaudioprocess = (e) => this._handleAudio(e);

    this.source.connect(this.processor);

    // Route through a silent gain node (required for onaudioprocess to
    // fire in some browsers) without actually playing the mic back.
    this.muteGain = this.audioContext.createGain();
    this.muteGain.gain.value = 0;
    this.processor.connect(this.muteGain);
    this.muteGain.connect(this.audioContext.destination);
  }

  stop() {
    // Flush whatever utterance was still in progress.
    if (this.speaking && this.chunks.length) {
      this._finalizeSegment();
    }

    this.processor?.disconnect();
    this.source?.disconnect();
    this.muteGain?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    this.audioContext?.close();

    this.processor = null;
    this.source = null;
    this.muteGain = null;
    this.stream = null;
    this.audioContext = null;
    this.speaking = false;
    this.chunks = [];
    this.silenceStartedAt = null;
  }

  _handleAudio(e) {
    const input = e.inputBuffer.getChannelData(0);
    const rms = computeRMS(input);
    this.onLevel?.(rms);

    const now = performance.now();
    const isLoud = rms > SILENCE_RMS_THRESHOLD;

    if (isLoud) {
      if (!this.speaking) {
        this.speaking = true;
        this.speechStartedAt = now;
        this.chunks = [];
        this.onSpeechStart?.();
      }
      this.silenceStartedAt = null;
      this.chunks.push(input.slice());
      return;
    }

    if (!this.speaking) return; // quiet, and nothing being recorded — ignore

    // Speaking, but this chunk is quiet — keep a little trailing audio so
    // words don't get clipped, then decide whether to close the utterance.
    this.chunks.push(input.slice());

    if (this.silenceStartedAt === null) {
      this.silenceStartedAt = now;
    }

    const silenceDuration = now - this.silenceStartedAt;
    const speechDuration = now - this.speechStartedAt;

    if (silenceDuration > SILENCE_HOLD_MS || speechDuration > MAX_SEGMENT_MS) {
      if (speechDuration >= MIN_SPEECH_MS) {
        this._finalizeSegment();
      } else {
        // too short to be real speech — drop it
        this.chunks = [];
        this.speaking = false;
        this.silenceStartedAt = null;
      }
    }
  }

  _finalizeSegment() {
    const nativeRate = this.audioContext.sampleRate;
    const merged = concatFloat32(this.chunks);
    this.chunks = [];
    this.speaking = false;
    this.silenceStartedAt = null;
    this.onSpeechEnd?.();

    try {
      const resampled = downsample(merged, nativeRate, TARGET_SAMPLE_RATE);
      const pcm16 = floatTo16BitPCM(resampled);
      const blob = encodeWAV(pcm16, TARGET_SAMPLE_RATE);
      this.onSegment?.(blob);
    } catch (err) {
      this.onError?.("Could not process recorded audio: " + err.message);
    }
  }
}

function computeRMS(float32Array) {
  let sum = 0;
  for (let i = 0; i < float32Array.length; i++) {
    sum += float32Array[i] * float32Array[i];
  }
  return Math.sqrt(sum / float32Array.length);
}

function concatFloat32(chunks) {
  const length = chunks.reduce((sum, c) => sum + c.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.length;
  }
  return result;
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

function encodeWAV(int16Array, sampleRate) {
  const bytesPerSample = 2;
  const blockAlign = bytesPerSample; // mono
  const byteRate = sampleRate * blockAlign;
  const dataSize = int16Array.length * bytesPerSample;
  const buffer = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM fmt chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, byteRate, true);
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, 16, true); // bits per sample
  writeString(view, 36, "data");
  view.setUint32(40, dataSize, true);

  let offset = 44;
  for (let i = 0; i < int16Array.length; i++, offset += 2) {
    view.setInt16(offset, int16Array[i], true);
  }

  return new Blob([buffer], { type: "audio/wav" });
}

function writeString(view, offset, str) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i));
  }
}