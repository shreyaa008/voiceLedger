# WebSocket bridge: Browser mic  <->  FastAPI  <->  Azure Voice Live
#
# Replaces pyaudio (physical mic/speaker) with a WebSocket connection
# to the browser. Reuses the exact session config from voice_assistant.py.
#
# Frontend connects to:  ws://localhost:8000/ws/voice
# Frontend sends:   binary WebSocket messages, each one a chunk of
#                    16-bit PCM audio at 24kHz, mono (same format
#                    Voice Live expects from pyaudio today)
# Frontend receives: binary WebSocket messages = audio to play back

import base64
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioNoiseReduction,
    AzureStandardVoice,
    AudioInputTranscriptionOptions,
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    AzureSemanticVadMultilingual,
)

load_dotenv()
router = APIRouter()


def build_session() -> RequestSession:
    """Same session config as voice_assistant.py, just pulled into its own function."""
    return RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=(
            "You are VoiceLedger, an AI bookkeeping assistant for Indian shopkeepers. "
            "You help users manage customers, credits, payments, balances and ledgers. "
            "You understand Hindi, English and Hinglish. "
            "LANGUAGE RULE: If the user speaks Hindi, answer in Hindi. "
            "If the user speaks English, answer in English. "
            "If the user speaks Hinglish, answer naturally in Hinglish. "
            "Never translate Hindi to English unless explicitly asked. "
            "Keep answers concise. For bookkeeping requests, clearly identify "
            "customer name, amount and transaction type. "
            "Do not invent transaction information."
        ),
        voice=AzureStandardVoice(name="en-US-Ava:DragonHDLatestNeural"),
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        input_audio_transcription=AudioInputTranscriptionOptions(
            model="azure-speech",
            language="hi-IN,en-IN",
            phrase_list=["VoiceLedger", "Ramesh", "Suresh", "udhaar", "baaki"],
        ),
        turn_detection=AzureSemanticVadMultilingual(
            threshold=0.5,
            prefix_padding_ms=500,
            silence_duration_ms=700,
            speech_duration_ms=100,
            create_response=True,
            interrupt_response=True,
        ),
        input_audio_echo_cancellation=AudioEchoCancellation(),
        input_audio_noise_reduction=AudioNoiseReduction(type="azure_deep_noise_suppression"),
    )


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()

    endpoint = os.getenv("AZURE_VOICELIVE_ENDPOINT")
    api_key = os.getenv("AZURE_VOICELIVE_API_KEY")
    model = os.getenv("AZURE_VOICELIVE_MODEL", "gpt-4o")
    api_version = os.getenv("AZURE_VOICELIVE_API_VERSION", "2026-04-10")

    if not endpoint or not api_key:
        await websocket.close(code=1011, reason="Azure Voice Live credentials missing")
        return

    async with connect(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
        model=model,
        api_version=api_version,
    ) as connection:

        await connection.session.update(session=build_session())

        async def receive_from_browser():
            """Browser mic chunks -> Azure"""
            try:
                while True:
                    chunk = await websocket.receive_bytes()
                    audio_b64 = base64.b64encode(chunk).decode("utf-8")
                    await connection.input_audio_buffer.append(audio=audio_b64)
            except WebSocketDisconnect:
                pass

        async def send_to_browser():
            """Azure audio replies -> browser"""
            async for event in connection:
                if event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
                    await websocket.send_bytes(event.delta)

                elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    transcript = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "transcript", "text": transcript})

                elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                    text = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "assistant_text", "text": text})

                elif event.type == ServerEventType.ERROR:
                    msg = getattr(event.error, "message", str(event.error))
                    await websocket.send_json({"type": "error", "message": msg})

        # run both directions at once, stop when either ends
        import asyncio
        receiver = asyncio.create_task(receive_from_browser())
        sender = asyncio.create_task(send_to_browser())
        done, pending = await asyncio.wait(
            {receiver, sender}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()