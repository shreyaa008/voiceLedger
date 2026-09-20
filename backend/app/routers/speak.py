from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.azure_speech import synthesize_speech

router = APIRouter()


class SpeakRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/speak")
async def speak(request: SpeakRequest):

    try:
        audio_data = synthesize_speech(
            request.text,
            request.language
        )

        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )