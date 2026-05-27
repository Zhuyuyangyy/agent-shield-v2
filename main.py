"""FastAPI application entry point"""
from fastapi import FastAPI
app = FastAPI(title="agent-shield-v2")
@app.get("/health")
async def health(): return {"status": "ok"}
