# TODO: Azure AI Speech SDK setup (STT + TTS), Hindi + English
import os

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

load_dotenv()


def transcribe_audio(file_path: str) -> dict:
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY is missing from .env")

    if not speech_region:
        raise RuntimeError("AZURE_SPEECH_REGION is missing from .env")

    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region,
    )

    audio_config = speechsdk.audio.AudioConfig(
        filename=file_path
    )

    # VoiceLedger supports Hindi and English
    auto_detect_language = (
        speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
            languages=["en-US", "hi-IN"]
        )
    )

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        auto_detect_source_language_config=auto_detect_language,
        audio_config=audio_config,
    )

    result = recognizer.recognize_once_async().get()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        detected_language = (
            speechsdk.AutoDetectSourceLanguageResult(result)
            .language
        )

        return {
            "text": result.text,
            "language": detected_language,
        }

    if result.reason == speechsdk.ResultReason.NoMatch:
        raise RuntimeError("No speech could be recognized")

    if result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details

        if cancellation.reason == speechsdk.CancellationReason.Error:
            raise RuntimeError(
                f"Speech recognition error: "
                f"{cancellation.error_details}"
            )

        raise RuntimeError(
            f"Speech recognition canceled: {cancellation.reason}"
        )

    raise RuntimeError("Unknown speech recognition result")
def synthesize_speech(text: str, language: str = "en") -> bytes:
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY is missing from .env")

    if not speech_region:
        raise RuntimeError("AZURE_SPEECH_REGION is missing from .env")

    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region,
    )

    if language == "hi":
        speech_config.speech_synthesis_voice_name = "hi-IN-SwaraNeural"
    else:
        speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"

    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff24Khz16BitMonoPcm
    )

    print("TTS language:", language)
    print("TTS voice:", speech_config.speech_synthesis_voice_name)
    print("TTS region:", speech_region)

    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None
    )

    result = synthesizer.speak_text_async(text).get()

    print("TTS result reason:", result.reason)
    print("TTS audio bytes:", len(result.audio_data))

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        return result.audio_data

    if result.reason == speechsdk.ResultReason.Canceled:
        cancellation = result.cancellation_details

        print("TTS cancellation reason:", cancellation.reason)
        print("TTS error code:", cancellation.error_code)
        print("TTS error details:", cancellation.error_details)

        raise RuntimeError(
            f"Speech synthesis failed. "
            f"Error code: {cancellation.error_code}. "
            f"Details: {cancellation.error_details}"
        )

    raise RuntimeError("Unknown speech synthesis result")
def translate_speech(
    file_path: str,
    from_language: str,
    to_language: str
) -> dict:

    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY is missing from .env")

    if not speech_region:
        raise RuntimeError("AZURE_SPEECH_REGION is missing from .env")

    translation_config = speechsdk.translation.SpeechTranslationConfig(
        subscription=speech_key,
        region=speech_region
    )

    translation_config.speech_recognition_language = from_language
    translation_config.add_target_language(to_language)

    audio_config = speechsdk.audio.AudioConfig(
        filename=file_path
    )

    recognizer = speechsdk.translation.TranslationRecognizer(
        translation_config=translation_config,
        audio_config=audio_config
    )

    result = recognizer.recognize_once_async().get()

    if result.reason == speechsdk.ResultReason.TranslatedSpeech:

        translated_text = result.translations.get(to_language)

        return {
            "original_text": result.text,
            "translated_text": translated_text,
            "source_language": from_language,
            "target_language": to_language
        }

    if result.reason == speechsdk.ResultReason.NoMatch:
        raise RuntimeError(
            "No speech could be recognized"
        )

    if result.reason == speechsdk.ResultReason.Canceled:

        cancellation = result.cancellation_details

        raise RuntimeError(
            f"Speech translation canceled: "
            f"{cancellation.error_details}"
        )

    raise RuntimeError(
        "Unknown speech translation result"
    )