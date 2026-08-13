import os

import uvicorn
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Sessions live in a local SQLite file for the spike. This is deliberately
# throwaway: Cloud Run's filesystem is ephemeral, so sessions do not survive a
# revision. Firestore-backed sessions come with the real build.
SESSION_SERVICE_URI = "sqlite+aiosqlite:///./sessions.db"

ALLOWED_ORIGINS = ["http://localhost", "http://localhost:8080", "*"]
SERVE_WEB_INTERFACE = True

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_SERVICE_URI,
    allow_origins=ALLOWED_ORIGINS,
    web=SERVE_WEB_INTERFACE,
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "model": os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
