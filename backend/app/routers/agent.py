# POST /ask â€” send question to the Foundry Agent (via agent/ MCP tools)
from fastapi import APIRouter

router = APIRouter()

@router.post(`"/ask`")
async def ask():
    # TODO: forward question to the Foundry Agent, return its answer
    return {`"answer`": `"TODO`"}
