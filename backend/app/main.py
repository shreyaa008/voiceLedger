from fastapi import FastAPI
from app.routers import transcribe, extract, transactions, speak, agent

app = FastAPI(title=`"VoiceLedger API`")

app.include_router(transcribe.router)
app.include_router(extract.router)
app.include_router(transactions.router)
app.include_router(speak.router)
app.include_router(agent.router)

@app.get(`"/`")
async def root():
    return {`"status`": `"VoiceLedger API running`"}
