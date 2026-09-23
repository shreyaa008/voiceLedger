from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    transcribe,
    extract,
    transactions,
    speak,
    translation,
    agent,
    voice_live,
    dashboard,
    shopkeepers,
)

app = FastAPI(
    title="VoiceLedger API",
    description="Backend API for the VoiceLedger AI bookkeeping application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # your Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcribe.router)
app.include_router(extract.router)
app.include_router(transactions.router)
app.include_router(speak.router)
app.include_router(translation.router)
app.include_router(agent.router)
app.include_router(voice_live.router)
app.include_router(dashboard.router)
app.include_router(shopkeepers.router)


@app.get("/")
async def root():
    return {"status": "VoiceLedger API running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}