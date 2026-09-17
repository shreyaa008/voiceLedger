# POST /speak â€” convert text to speech (Azure TTS)
from fastapi import APIRouter

router = APIRouter()

@router.post(`"/speak`")
async def speak():
    # TODO: call Azure AI Speech Text-to-Speech
    return {`"audio_url`": None}
