# WebSocket bridge: Browser mic  <->  FastAPI  <->  Azure Voice Live
#
# Replaces pyaudio (physical mic/speaker) with a WebSocket connection
# to the browser. This is the ASK pipeline — full-duplex conversational
# voice, grounded in real ledger data via the MCP tools below. (Entries
# use a separate, lighter batch-STT pipeline — see routers/transcribe.py
# and routers/transactions.py — Voice Live is deliberately not used there.)
#
# Frontend connects to:  ws://localhost:8000/ws/voice
# Frontend sends:   binary WebSocket messages, each one a chunk of
#                    16-bit PCM audio at 24kHz, mono (same format
#                    Voice Live expects from pyaudio today)
# Frontend receives: binary WebSocket messages = audio to play back,
#                     plus JSON messages for transcript/tool/error events.

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioNoiseReduction,
    AzureStandardVoice,
    AudioInputTranscriptionOptions,
    FunctionCallOutputItem,
    FunctionTool,
    InputAudioFormat,
    Modality,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    AzureSemanticVadMultilingual,
)

# Ensure project root is in sys.path when running from backend directory
# (same pattern as routers/agent.py, since this also calls into agent/).
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.mcp_server import list_tools, call_tool
from agent.agent_config import get_system_prompt

load_dotenv()
router = APIRouter()


def build_tools() -> list:
    """Expose the same MCP tools the text agent uses (agent/mcp_server.py),
    so Voice Live answers are grounded in real Supabase data instead of the
    model improvising a number."""
    return [
        FunctionTool(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["inputSchema"],
        )
        for tool in list_tools()
    ]


def build_session() -> RequestSession:
    """Same session config as voice_assistant.py, plus the MCP tools."""
    instructions = (
        get_system_prompt()
        + "\n\n## Voice call rules\n"
        + "You are speaking with the shopkeeper live, over voice, in a phone call. "
        "You understand Hindi, English and Hinglish. "
        "LANGUAGE RULE: If the user speaks Hindi, answer in Hindi. "
        "If the user speaks English, answer in English. "
        "If the user speaks Hinglish, answer naturally in Hinglish. "
        "Never translate Hindi to English unless explicitly asked. "
        "Keep answers short and conversational, like a real spoken reply — "
        "no bullet points, no reading out raw JSON. "
        "Always call the relevant tool before answering a question about a "
        "customer, balance, risk, or reminder — never guess a number."
    )

    return RequestSession(
        modalities=[Modality.TEXT, Modality.AUDIO],
        instructions=instructions,
        voice=AzureStandardVoice(name="en-US-Ava:DragonHDLatestNeural"),
        input_audio_format=InputAudioFormat.PCM16,
        output_audio_format=OutputAudioFormat.PCM16,
        input_audio_transcription=AudioInputTranscriptionOptions(
            model="azure-speech",
            language="hi-IN,en-IN",
            phrase_list=["VoiceLedger", "udhaar", "baaki", "hisaab"],
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
        tools=build_tools(),
        tool_choice="auto",
    )


async def _handle_tool_call(connection, websocket: WebSocket, event) -> None:
    """A function_call_arguments.done event means the model wants to call
    one of our MCP tools. Run it for real, tell the browser (so the call UI
    can show "checking Utkarsh's ledger..."), then feed the result back into
    the session so the model's spoken answer is grounded in it."""
    try:
        arguments = json.loads(event.arguments) if event.arguments else {}
    except json.JSONDecodeError:
        arguments = {}

    await websocket.send_json({
        "type": "tool_call",
        "name": event.name,
        "arguments": arguments,
    })

    # The MCP tools use the synchronous Supabase client — run off the event
    # loop thread so a slow DB call doesn't stall the audio stream.
    result = await asyncio.to_thread(call_tool, event.name, arguments)

    await websocket.send_json({
        "type": "tool_result",
        "name": event.name,
        "data": result,
    })

    await connection.conversation.item.create(
        item=FunctionCallOutputItem(
            call_id=event.call_id,
            output=json.dumps(result, default=str),
        )
    )
    await connection.response.create()


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
            """Azure audio replies + tool grounding -> browser"""
            async for event in connection:
                if event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
                    await websocket.send_bytes(event.delta)

                elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    transcript = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "transcript", "text": transcript})

                elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                    text = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "assistant_text", "text": text})

                elif event.type == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
                    await _handle_tool_call(connection, websocket, event)

                elif event.type == ServerEventType.ERROR:
                    msg = getattr(event.error, "message", str(event.error))
                    await websocket.send_json({"type": "error", "message": msg})

        # run both directions at once, stop when either ends
        receiver = asyncio.create_task(receive_from_browser())
        sender = asyncio.create_task(send_to_browser())
        done, pending = await asyncio.wait(
            {receiver, sender}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()