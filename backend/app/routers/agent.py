from fastapi import APIRouter

router = APIRouter()


@router.post("/ask")
async def ask():
    # TODO: forward question to the Foundry Agent
    return {
        "answer": "TODO"
    }