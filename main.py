import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# === FastAPI импорты ===
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# === Telegram Bot импорты ===
import yt_dlp
from youtube_search import YoutubeSearch
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup

# === 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DOWNLOAD_DIR = "downloads/"

# === 2. ИНИЦИАЛИЗАЦИЯ SPOTIFY ===
sp = spotipy.Spotify(
    client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

# === 3. FASTAPI ВЕБ-СЕРВЕР (для Mini App) ===
app = FastAPI(title="Music Finder Bot & Mini App")

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

def save_playlists(data):
    with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Mini App not found</h1>", status_code=404)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Server is running!"}

@app.get("/api/playlists")
async def get_playlists(user_id: str = Query(...)):
    return load_playlists().get(user_id, {})

@app.get("/api/playlist")
async def get_playlist(user_id: str = Query(...), name: str = Query(...)):
    return load_playlists().get(user_id, {}).get(name, [])

# === 4. TELEGRAM БОТ ===
dp = Dispatcher()
bot = None
last_track = {}

def search_spotify(query):
    try:
        results = sp.search(q=query, limit=1, type='track')
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            return f"{track['artists'][0]['name']} - {track['name']}"
    except Exception as e:
        print(f"Spotify error: {e}")
    return None

def search_youtube(query):
    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if results:
            return f"https://www.youtube.com/watch?v={results[0]['id']}"
    except Exception as e:
        print(f"YouTube error: {e}")
    return None

def download_mp3(youtube_url, output_path=DOWNLOAD_DIR):
    os.makedirs(output_path, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}],
        'outtmpl': f'{output_path}%(title)s.%(ext)s',
        'quiet': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        return ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    first_name = message.from_user.first_name or "Пользователь"
    webapp_url = os.getenv("WEBAPP_URL", "https://music-finder-bot-2xi8.onrender.com")
    
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=" Открыть приложение", web_app=WebAppInfo(url=webapp_url))]],
        resize_keyboard=True
    )
    await message.answer(f" Привет, {first_name}! Отправь название трека для поиска или открой Mini App.", reply_markup=kb)

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_message(message: types.Message):
    query = message.text
    status_msg = await message.answer(f"🔍 Ищу: {query}")
    
    spotify_name = search_spotify(query)
    yt_url = search_youtube(spotify_name or query)
    
    if not yt_url:
        await status_msg.edit_text("❌ Трек не найден.")
        return
    
    await status_msg.edit_text("⬇️ Скачиваю...")
    
    try:
        filename = download_mp3(yt_url)
        last_track[message.from_user.id] = {"name": spotify_name or query}
        
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text("❌ Файл слишком большой (>50 МБ).")
            os.remove(filename)
            return

        pl_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ В плейлист", callback_data="pl_menu")
        ]])
        
        await message.answer_audio(
            audio=types.FSInputFile(filename),
            caption=f"🎵 {spotify_name or query}",
            reply_markup=pl_kb
        )
        await status_msg.edit_text("✅ Готово!")
        os.remove(filename)
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Ошибка: {e}")

@dp.message(Command("new"))
async def cmd_new(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /new Название")
        return
    name = parts[1].strip()
    data = load_playlists()
    uid = str(message.from_user.id)
    data.setdefault(uid, {})
    if name in data[uid]:
        await message.answer(f"Плейлист «{name}» уже существует.")
        return
    data[uid][name] = []
    save_playlists(data)
    await message.answer(f"✅ Плейлист «{name}» создан!")

@dp.callback_query(lambda c: c.data == "pl_menu")
async def pl_menu(callback: types.CallbackQuery):
    data = load_playlists()
    pls = data.get(str(callback.from_user.id), {})
    if not pls:
        await callback.answer("Сначала создайте плейлист: /new Название", show_alert=True)
        return
    rows = [[InlineKeyboardButton(text=f"📁 {name}", callback_data=f"pl_add:{name}")] for name in pls.keys()]
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer("Выберите плейлист")

@dp.callback_query(lambda c: c.data.startswith("pl_add:"))
async def pl_add(callback: types.CallbackQuery):
    name = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    track_info = last_track.get(uid)
    if not track_info:
        await callback.answer("Сначала скачайте трек!", show_alert=True)
        return
    
    data = load_playlists()
    udata = data.setdefault(str(uid), {})
    if name not in udata:
        await callback.answer("Плейлист не найден", show_alert=True)
        return
    
    track_name = track_info.get("name", "Неизвестный")
    if any(t.get("name") == track_name for t in udata[name]):
        await callback.answer("Уже есть в этом плейлисте", show_alert=True)
        return
    
    udata[name].append({"name": track_name})
    save_playlists(data)
    await callback.answer(f"Добавлено в «{name}»")

# === 5. ЗАПУСК ОБОИХ ПРОЦЕССОВ ===
async def start_bot():
    global bot
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    print("✅ Telegram бот запущен!")
    await dp.start_polling(bot)

async def main():
    port = int(os.getenv("PORT", 8000))
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    
    print(f"🚀 Запуск сервера на порту {port} и бота...")
    await asyncio.gather(
        server.serve(),
        start_bot()
    )

if __name__ == "__main__":
    asyncio.run(main())