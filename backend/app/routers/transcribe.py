# POST /transcribe â€” send audio to Azure AI Speech, return text
from fastapi import APIRouter

router = APIRouter()

@router.post(`"/transcribe`")
async def transcribe():
    # TODO: call Azure AI Speech Speech-to-Text
    return {`"text`": `"TODO`"}
