import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.azure_speech import translate_speech

router = APIRouter()


@router.post("/translate")
async def translate(
    file: UploadFile = File(...),
    from_language: str = "hi-IN",
    to_language: str = "en"
):
    temp_path = None

    try:
        suffix = os.path.splitext(
            file.filename or ""
        )[1] or ".wav"

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:

            temp_path = temp_file.name

            content = await file.read()
            temp_file.write(content)

        result = translate_speech(
            temp_path,
            from_language,
            to_language
        )

        return {
            "success": True,
            "filename": file.filename,
            **result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)