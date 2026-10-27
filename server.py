import os
import json
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI(title="Music Finder Mini App Server")

# CORS для Telegram
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "mini_app"
PLAYLISTS_FILE = BASE_DIR / "playlists.json"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def load_playlists():
    if PLAYLISTS_FILE.exists():
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Mini App not found</h1>", status_code=404)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Server is running!"}

# === НОВЫЕ API ДЛЯ MINI APP ===
@app.get("/api/playlists")
async def get_playlists(user_id: str = Query(...)):
    data = load_playlists()
    return data.get(user_id, {})

@app.get("/api/playlist")
async def get_playlist(user_id: str = Query(...), name: str = Query(...)):
    data = load_playlists()
    return data.get(user_id, {}).get(name, [])