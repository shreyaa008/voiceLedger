# POST /extract — entity extraction from transcribed text (Azure AI Language)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.azure_language import extract_transaction

router = APIRouter()


class ExtractRequest(BaseModel):
    text: str
    language: str = "en"


@router.post("/extract")
async def extract(request: ExtractRequest):
    try:
        result = extract_transaction(request.text, request.language)
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))