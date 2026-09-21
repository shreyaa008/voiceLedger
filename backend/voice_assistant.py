import asyncio
import base64
import os
import queue

import pyaudio
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import (
    AudioEchoCancellation,
    AudioNoiseReduction,
    AzureStandardVoice,
    InputAudioFormat,
    OutputAudioFormat,
    RequestSession,
    ServerEventType,
    ServerVad,
    Modality,
    AudioInputTranscriptionOptions,
)

load_dotenv()


class AudioProcessor:
    def __init__(self, connection, loop):
        self.connection = connection
        self.loop = loop

        self.audio = pyaudio.PyAudio()

        # Audio configuration
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 24000
        self.chunk_size = 1200

        self.input_stream = None
        self.output_stream = None

        self.playback_queue = queue.Queue()

    def start_microphone(self):
        def callback(in_data, frame_count, time_info, status):
            try:
                audio_base64 = base64.b64encode(in_data).decode("utf-8")

                asyncio.run_coroutine_threadsafe(
                    self.connection.input_audio_buffer.append(
                        audio=audio_base64
                    ),
                    self.loop,
                )

            except Exception as e:
                print("❌ Microphone callback error:", e)

            return (None, pyaudio.paContinue)

        self.input_stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=callback,
        )

        print("🎤 Microphone started")

    def start_speaker(self):
        def callback(in_data, frame_count, time_info, status):
            bytes_needed = (
                frame_count
                * pyaudio.get_sample_size(self.format)
            )

            output = b""

            while len(output) < bytes_needed:
                try:
                    data = self.playback_queue.get_nowait()
                    output += data

                except queue.Empty:
                    break

            if len(output) < bytes_needed:
                output += b"\x00" * (
                    bytes_needed - len(output)
                )

            return output[:bytes_needed], pyaudio.paContinue

        self.output_stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            output=True,
            frames_per_buffer=self.chunk_size,
            stream_callback=callback,
        )

        print("🔊 Speaker started")

    def queue_audio(self, audio_data):
        self.playback_queue.put(audio_data)

    def shutdown(self):
        if self.input_stream:
            self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None

        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None

        self.audio.terminate()


async def main():

    # =========================================================
    # ENVIRONMENT VARIABLES
    # =========================================================

    endpoint = os.getenv("AZURE_VOICELIVE_ENDPOINT")

    api_key = os.getenv(
        "AZURE_VOICELIVE_API_KEY"
    )

    model = os.getenv(
        "AZURE_VOICELIVE_MODEL",
        "gpt-4o"
    )

    api_version = os.getenv(
        "AZURE_VOICELIVE_API_VERSION",
        "2026-04-10"
    )

    if not endpoint:
        raise RuntimeError(
            "AZURE_VOICELIVE_ENDPOINT is missing"
        )

    if not api_key:
        raise RuntimeError(
            "AZURE_VOICELIVE_API_KEY is missing"
        )

    # =========================================================
    # START
    # =========================================================

    print()
    print("==========================================")
    print("VOICELEDGER - VOICE LIVE")
    print("==========================================")

    print("Endpoint:", endpoint)
    print("Model:", model)
    print("API Version:", api_version)
    print("Region: Korea Central")
    print()

    # =========================================================
    # CONNECT TO AZURE VOICE LIVE
    # =========================================================

    async with connect(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key),
        model=model,
        api_version=api_version,
    ) as connection:

        print("✅ Voice Live connected!")

        loop = asyncio.get_running_loop()

        audio = AudioProcessor(
            connection,
            loop
        )

        # =====================================================
        # VOICE
        # =====================================================

        voice = AzureStandardVoice(
            name="en-US-Ava:DragonHDLatestNeural"
        )

        # =====================================================
        # SERVER SIDE VAD
        # =====================================================

        turn_detection = ServerVad(
            threshold=0.5,
            prefix_padding_ms=400,
            silence_duration_ms=500,
        )

        # =====================================================
        # SESSION CONFIGURATION
        # =====================================================

        session = RequestSession(

            # -------------------------------------------------
            # TEXT + AUDIO
            # -------------------------------------------------

            modalities=[
                Modality.TEXT,
                Modality.AUDIO,
            ],

            # -------------------------------------------------
            # AI INSTRUCTIONS
            # -------------------------------------------------

            instructions=(
                "You are VoiceLedger, an AI bookkeeping assistant "
                "for Indian shopkeepers. "

                "You help shopkeepers manage customers, "
                "credits, payments, balances and ledger information. "

                "You understand Hindi, English and Hinglish. "

                "IMPORTANT LANGUAGE RULE: "
                "Always reply in the same language that the user is speaking. "

                "If the user speaks Hindi, reply in Hindi. "

                "If the user speaks English, reply in English. "

                "If the user speaks Hinglish, reply naturally in Hinglish. "

                "Do NOT translate Hindi into English unless the user "
                "specifically asks for translation. "

                "Use natural Indian Hindi when speaking Hindi. "

                "Keep answers short, clear and conversational. "

                "Do not unnecessarily repeat the user's sentence. "

                "For bookkeeping requests, clearly mention the "
                "customer name, amount and transaction type when relevant."
            ),

            # -------------------------------------------------
            # OUTPUT VOICE
            # -------------------------------------------------

            voice=voice,

            # -------------------------------------------------
            # INPUT AUDIO
            # -------------------------------------------------

            input_audio_format=InputAudioFormat.PCM16,

            # -------------------------------------------------
            # OUTPUT AUDIO
            # -------------------------------------------------

            output_audio_format=OutputAudioFormat.PCM16,

            # -------------------------------------------------
            # AZURE SPEECH TRANSCRIPTION
            # -------------------------------------------------

            input_audio_transcription=AudioInputTranscriptionOptions(
                model="azure-speech",
                language="hi-IN,en-IN",
            ),

            # -------------------------------------------------
            # VOICE ACTIVITY DETECTION
            # -------------------------------------------------

            turn_detection=turn_detection,

            # -------------------------------------------------
            # ECHO CANCELLATION
            # -------------------------------------------------

            input_audio_echo_cancellation=(
                AudioEchoCancellation()
            ),

            # -------------------------------------------------
            # NOISE REDUCTION
            # -------------------------------------------------

            input_audio_noise_reduction=(
                AudioNoiseReduction(
                    type="azure_deep_noise_suppression"
                )
            ),
        )

        # =====================================================
        # UPDATE SESSION
        # =====================================================

        await connection.session.update(
            session=session
        )

        print("✅ Session configured")

        # =====================================================
        # START SPEAKER
        # =====================================================

        audio.start_speaker()

        session_ready = False

        print()
        print("==========================================")
        print("🎤 VOICELEDGER READY")
        print("==========================================")

        print("Speak into your microphone.")

        print()
        print("Hindi example:")
        print("  'Ramesh ne paanch sau rupaye diye'")

        print("English example:")
        print("  'Ramesh paid five hundred rupees'")

        print("Hinglish example:")
        print("  'Ramesh ka balance batao'")

        print()
        print("Press Ctrl+C to stop.")
        print("==========================================")
        print()

        # =====================================================
        # EVENT LOOP
        # =====================================================

        try:

            async for event in connection:

                # -------------------------------------------------
                # SESSION UPDATED
                # -------------------------------------------------

                if event.type == ServerEventType.SESSION_UPDATED:

                    print("✅ Voice session ready")

                    if not session_ready:

                        session_ready = True

                        audio.start_microphone()

                # -------------------------------------------------
                # USER STARTED SPEAKING
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STARTED
                ):

                    print("🎤 Listening...")

                # -------------------------------------------------
                # USER STOPPED SPEAKING
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.INPUT_AUDIO_BUFFER_SPEECH_STOPPED
                ):

                    print("🤔 Processing...")

                # -------------------------------------------------
                # ASSISTANT RESPONSE STARTED
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.RESPONSE_CREATED
                ):

                    print("🤖 Assistant responding...")

                # -------------------------------------------------
                # ASSISTANT AUDIO
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.RESPONSE_AUDIO_DELTA
                ):

                    audio.queue_audio(
                        event.delta
                    )

                # -------------------------------------------------
                # ASSISTANT AUDIO FINISHED
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.RESPONSE_AUDIO_DONE
                ):

                    print(
                        "🔊 Assistant finished speaking"
                    )

                # -------------------------------------------------
                # RESPONSE COMPLETED
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.RESPONSE_DONE
                ):

                    print("🎤 Ready...")

                # -------------------------------------------------
                # CONVERSATION ITEM
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.CONVERSATION_ITEM_CREATED
                ):

                    item = event.item

                    try:

                        for content in item.content or []:

                            transcript = getattr(
                                content,
                                "transcript",
                                None
                            )

                            if transcript:

                                print(
                                    f"📝 Transcript: {transcript}"
                                )

                    except Exception as e:

                        print(
                            "⚠️ Transcript display error:",
                            e
                        )

                # -------------------------------------------------
                # ERROR
                # -------------------------------------------------

                elif (
                    event.type
                    == ServerEventType.ERROR
                ):

                    print(
                        "❌ Voice Live error:",
                        event.error.message
                    )

        except KeyboardInterrupt:

            print()
            print("Stopping VoiceLedger...")

        finally:

            audio.shutdown()

            print(
                "Audio devices closed."
            )


# =============================================================
# PROGRAM ENTRY POINT
# =============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "\nVoiceLedger stopped."
        )