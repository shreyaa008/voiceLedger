# POST /transcribe â€” send audio to Azure AI Speech, return text
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.azure_speech import transcribe_audio

router = APIRouter()


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...)
):
    temp_path = None

    try:
        suffix = os.path.splitext(file.filename or "")[1] or ".wav"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:
            temp_path = temp_file.name

            content = await file.read()
            temp_file.write(content)

        result = transcribe_audio(temp_path)

        return {
            "success": True,
            "filename": file.filename,
            "text": result["text"],
            "language": result["language"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)