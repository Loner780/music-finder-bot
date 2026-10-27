from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="mini_app"), name="static")

PLAYLISTS_FILE = "playlists.json"

def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        try:
            with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            print(f"Ошибка чтения: {e}")
            try:
                with open(PLAYLISTS_FILE, "r", encoding="utf-16") as f:
                    data = json.load(f)
                    return data
            except Exception as e2:
                print(f"Ошибка UTF-16: {e2}")
    return {}

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("mini_app/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/playlists")
async def get_playlists(user_id: int):
    data = load_playlists()
    return data.get(str(user_id), {})

@app.get("/api/playlist")
async def get_playlist(user_id: int, name: str):
    data = load_playlists()
    user_data = data.get(str(user_id), {})
    return user_data.get(name, [])

if __name__ == "__main__":
    import uvicorn
    print("Server started! Open: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)