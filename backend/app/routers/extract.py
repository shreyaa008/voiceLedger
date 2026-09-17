from fastapi import APIRouter

router = APIRouter()


@router.post("/extract")
async def extract():
    # TODO: call Azure AI Language entity extraction
    return {
        "customer": None,
        "amount": None,
        "type": None,
        "date": None
    }