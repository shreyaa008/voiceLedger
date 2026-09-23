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
import contextlib
import json
import logging
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
logger = logging.getLogger("voiceledger.voice_live")

# How long we'll wait for Azure to confirm our session.update() before
# giving up and telling the browser something is wrong, instead of leaving
# the call UI stuck forever.
SESSION_READY_TIMEOUT_S = 10


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
        # "en-US-Ava:DragonHDLatestNeural" is a single-language HD voice —
        # it does not officially support code-switching, which is the root
        # cause of the "language switches unexpectedly" bug: when the model
        # emits Hindi/Hinglish text, that voice's language auto-detection is
        # unreliable and it drifts back to (or randomly switches into)
        # English. "en-US-AvaMultilingualNeural" is the multilingual
        # counterpart of the same voice character, built to speak whichever
        # language the text is in. We leave `locale` unset so it keeps
        # auto-detecting per sentence (setting it would force one language
        # and mute the others), and bias the English accent toward Indian
        # English via prefer_locales without touching Hindi output.
        voice=AzureStandardVoice(
            name="en-US-AvaMultilingualNeural",
            prefer_locales=["en-IN"],
        ),
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


async def _handle_tool_call(connection, websocket: WebSocket, event, shopkeeper_id: str) -> None:
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
    # loop thread so a slow DB call doesn't stall the audio stream. If the
    # tool itself raises (bad args, DB hiccup, etc.) we still have to answer
    # Azure's function call with *something*, or the model just hangs
    # waiting for output and the call goes silent — so we feed back an
    # error payload instead of letting the exception escape.
    try:
        result = await asyncio.to_thread(call_tool, event.name, arguments, shopkeeper_id)
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see above
        logger.exception("Tool call %s failed", event.name)
        result = {"error": f"{event.name} failed: {exc}"}

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


async def _safe_send_json(websocket: WebSocket, payload: dict) -> None:
    """Best-effort JSON send — the browser side may already be gone by the
    time we try to report an error, and that must never itself raise."""
    with contextlib.suppress(Exception):
        await websocket.send_json(payload)


async def _fail(websocket: WebSocket, message: str, code: int = 1011) -> None:
    """Tell the browser clearly why the call can't proceed, THEN close.
    Closing first (the old behavior) throws away the reason: the frontend's
    onclose handler only sees a numeric close code, not `message`, so every
    setup failure looked like a silent hang."""
    logger.warning("Voice Live call failed: %s", message)
    await _safe_send_json(websocket, {"type": "error", "message": message})
    with contextlib.suppress(Exception):
        await websocket.close(code=code, reason=message[:120])


@router.websocket("/ws/voice")
async def voice_ws(websocket: WebSocket):
    await websocket.accept()

    # Root cause of the ledger/customer lookup failures: shopkeeper_id was
    # never read from the connection, so every shopkeeper-scoped tool call
    # (get_customer_ledger, check_risk, generate_reminder,
    # get_business_summary) fell back to call_tool()'s shopkeeper_id=None
    # default and returned {"error": "No shopkeeper session — cannot look
    # up data."} — which the model then turned into a graceful-sounding
    # apology. The frontend sends it as a query param (see
    # frontend/src/components/AskAssistant.jsx); everything else about the
    # audio/WebSocket pipeline is unchanged.
    shopkeeper_id = websocket.query_params.get("shopkeeper_id")
    if not shopkeeper_id:
        await _fail(websocket, "Missing shopkeeper_id — cannot start a scoped Voice Live session.")
        return

    endpoint = os.getenv("AZURE_VOICELIVE_ENDPOINT")
    api_key = os.getenv("AZURE_VOICELIVE_API_KEY")
    model = os.getenv("AZURE_VOICELIVE_MODEL", "gpt-4o")
    api_version = os.getenv("AZURE_VOICELIVE_API_VERSION", "2026-04-10")

    if not endpoint or not api_key:
        await _fail(websocket, "Azure Voice Live credentials are missing on the server "
                                "(AZURE_VOICELIVE_ENDPOINT / AZURE_VOICELIVE_API_KEY).")
        return

    try:
        async with connect(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            model=model,
            api_version=api_version,
        ) as connection:
            await _run_call(connection, websocket, shopkeeper_id)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - connect()/session setup failed
        # This is what used to fail silently: a bad endpoint, an expired
        # key, an unsupported model/api-version, or Azure being unreachable
        # all raised here, FastAPI closed the socket with no explanation,
        # and the browser just saw the call go dead.
        logger.exception("Voice Live connection setup failed")
        await _fail(websocket, f"Could not start the Voice Live session: {exc}")


async def _run_call(connection, websocket: WebSocket, shopkeeper_id: str) -> None:
    """Runs one voice call end-to-end: configures the session, then bridges
    browser <-> Azure audio/events until either side disconnects."""

    session_ready = asyncio.Event()

    async def receive_from_browser():
        """Browser mic chunks -> Azure"""
        try:
            while True:
                chunk = await websocket.receive_bytes()
                # Wait for Azure to confirm session.update() before forwarding
                # any audio. session.update() only *sends* the config — it
                # does not wait for the session.updated ack — so without this
                # gate, mic audio captured right after the socket opens can
                # reach Azure before our instructions/voice/VAD/tools are
                # applied. Azure then processes it under stale/default
                # config, which is what caused "sometimes nothing happens",
                # "no response audio", and inconsistent language switching.
                await session_ready.wait()
                audio_b64 = base64.b64encode(chunk).decode("utf-8")
                await connection.input_audio_buffer.append(audio=audio_b64)
        except WebSocketDisconnect:
            pass
        except RuntimeError:
            # receive_bytes() called after the socket already closed.
            pass

    async def send_to_browser():
        """Azure audio replies + tool grounding -> browser"""
        try:
            async for event in connection:
                # print("AZURE EVENT:", event.type)
                if event.type == ServerEventType.SESSION_UPDATED:
                    if not session_ready.is_set():
                        session_ready.set()
                        # Tells the frontend it's now safe to start streaming
                        # mic audio and that the UI can leave "connecting".
                        await websocket.send_json({"type": "ready"})

                elif event.type == ServerEventType.RESPONSE_AUDIO_DELTA:
                    await websocket.send_bytes(event.delta)

                elif event.type == ServerEventType.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:
                    transcript = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "transcript", "text": transcript})

                elif event.type == ServerEventType.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                    text = getattr(event, "transcript", "")
                    await websocket.send_json({"type": "assistant_text", "text": text})

                elif event.type == ServerEventType.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE:
                    await _handle_tool_call(connection, websocket, event, shopkeeper_id)

                elif event.type == ServerEventType.ERROR:
                    msg = getattr(event.error, "message", str(event.error))
                    await websocket.send_json({"type": "error", "message": msg})
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # noqa: BLE001 - Azure connection dropped/errored mid-call
            logger.exception("Voice Live event loop failed")
            await _safe_send_json(websocket, {"type": "error", "message": f"Voice Live connection lost: {exc}"})

    async def watch_session_ready():
        """If Azure never acks session.update(), the UI would otherwise sit
        on "connecting" forever with no explanation. Time it out instead by
        reporting the problem and closing the socket, which naturally ends
        receive_from_browser/send_to_browser too. NOTE: this task must NOT
        be raced with FIRST_COMPLETED alongside the other two — it finishes
        successfully (silently) the moment the session becomes ready, which
        would otherwise be mistaken for "the call ended" and tear everything
        down right as it starts."""
        try:
            await asyncio.wait_for(session_ready.wait(), timeout=SESSION_READY_TIMEOUT_S)
        except asyncio.TimeoutError:
            await _safe_send_json(websocket, {
                "type": "error",
                "message": "Voice Live didn't confirm the session in time. Please try again.",
            })
            with contextlib.suppress(Exception):
                await websocket.close(code=1011, reason="session not ready in time")

    await connection.session.update(session=build_session())

    # run mic streaming and Azure event handling concurrently; stop both as
    # soon as either one ends. The readiness watchdog runs alongside them
    # but independently (see its docstring above) and is cancelled in the
    # `finally` below rather than raced here.
    receiver = asyncio.create_task(receive_from_browser())
    sender = asyncio.create_task(send_to_browser())
    watchdog = asyncio.create_task(watch_session_ready())

    try:
        done, pending = await asyncio.wait({receiver, sender}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        # surface exceptions from whichever task finished first, instead of
        # swallowing them (the old code never checked task results at all)
        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc and not isinstance(exc, WebSocketDisconnect):
                raise exc
    finally:
        watchdog.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await watchdog
        with contextlib.suppress(Exception):
            await websocket.close()