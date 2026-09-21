"""
Test client for /ws/voice — simulates what the browser will eventually do,
so you can confirm your Azure Voice Live credentials + WebSocket bridge
work BEFORE building any frontend audio code.

Usage:
    python test_voice_ws.py path/to/test_audio.wav

test_audio.wav must be 16-bit PCM, mono, 24000 Hz (same format the
browser will eventually send). Convert any audio file to this format
with ffmpeg:

    ffmpeg -i input.mp3 -ar 24000 -ac 1 -sample_fmt s16 test_audio.wav

Record a quick test clip in Hindi or English saying something like:
    "Ramesh ne paanch sau rupaye diye"
    "Ramesh paid five hundred rupees"

Requires:
    pip install websockets

Run this WHILE your backend (uvicorn app.main:app --reload) is running.
"""

import asyncio
import json
import sys
import wave

import websockets

WS_URL = "ws://127.0.0.1:8000/ws/voice"
CHUNK_MS = 100          # send audio in 100ms chunks, like a real mic stream
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2    # 16-bit


async def send_audio(ws, wav_path):
    with wave.open(wav_path, "rb") as wf:
        if (
            wf.getframerate() != SAMPLE_RATE
            or wf.getsampwidth() != BYTES_PER_SAMPLE
            or wf.getnchannels() != 1
        ):
            print("WARNING: file is not 16-bit mono 24kHz PCM — Azure may reject or mishear it.")
            print(f"  got: {wf.getframerate()}Hz, {wf.getsampwidth() * 8}-bit, {wf.getnchannels()} channel(s)")
            print("  fix with: ffmpeg -i input.wav -ar 24000 -ac 1 -sample_fmt s16 test_audio.wav")

        chunk_frames = int(SAMPLE_RATE * CHUNK_MS / 1000)
        data = wf.readframes(chunk_frames)
        while data:
            await ws.send(data)
            await asyncio.sleep(CHUNK_MS / 1000)
            data = wf.readframes(chunk_frames)

    print("Finished sending audio. Waiting for replies...")


async def receive_replies(ws, out_path="reply.wav"):
    audio_chunks = []
    try:
        async for message in ws:
            if isinstance(message, bytes):
                audio_chunks.append(message)
                print(f"[audio] received {len(message)} bytes")
            else:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    print("[text]", message)
                    continue

                msg_type = payload.get("type")
                if msg_type == "transcript":
                    print("[transcript]", payload.get("text"))
                elif msg_type == "assistant_text":
                    print("[assistant]", payload.get("text"))
                elif msg_type == "error":
                    print("[ERROR]", payload.get("message"))
                else:
                    print("[unknown]", payload)
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed by server.")

    if audio_chunks:
        with wave.open(out_path, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(BYTES_PER_SAMPLE)
            out.setframerate(SAMPLE_RATE)
            out.writeframes(b"".join(audio_chunks))
        print(f"\nSaved assistant's spoken reply to {out_path} — play it to confirm audio came back.")
    else:
        print("\nNo audio came back — check the terminal running uvicorn for errors.")


async def main(wav_path):
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        print("Connected. Sending audio...")
        send_task = asyncio.create_task(send_audio(ws, wav_path))
        recv_task = asyncio.create_task(receive_replies(ws))

        await send_task
        # give Azure a few seconds after audio ends to finish responding
        try:
            await asyncio.wait_for(recv_task, timeout=15)
        except asyncio.TimeoutError:
            print("Stopped waiting for more replies after 15s.")
            recv_task.cancel()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_voice_ws.py path/to/test_audio.wav")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))