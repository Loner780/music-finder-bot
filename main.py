import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import quote
import aiohttp

# === FastAPI импорты ===
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# === Telegram Bot импорты ===
import yt_dlp
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
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

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

# === СЛОВАРЬ ПЕРЕВОДОВ ===
LANGUAGES = {
    'ru': {
        'welcome': 'Привет, {name}! Я бот для поиска и скачивания музыки.',
        'search_prompt': 'Отправьте мне название трека или исполнителя, и я найду MP3 файл.',
        'open_app': '🎵 Открыть приложение',
        'choose_lang': 'Выберите язык / Choose language:',
        'lang_set_ru': '✅ Язык изменён на русский',
        'lang_set_en': '✅ Language set to English',
        'searching': '🔍 Ищу: {query}',
        'downloading': '⬇️ Скачиваю...',
        'done': '✅ Готово!',
        'not_found': '❌ Трек не найден.',
        'error': '⚠️ Ошибка: {e}',
        'too_big': '❌ Файл слишком большой (>50 МБ).',
        'add_to_playlist': '➕ В плейлист',
        'select_playlist': 'Выберите плейлист',
        'create_playlist_first': 'Сначала создайте плейлист: /new Название',
        'playlist_created': '✅ Плейлист «{name}» создан!',
        'playlist_exists': 'Плейлист «{name}» уже существует.',
        'usage_new': 'Использование: /new Название',
        'added_to_playlist': 'Добавлено в «{name}»',
        'no_track': 'Сначала скачайте трек!',
        'playlist_not_found': 'Плейлист не найден',
        'already_in_playlist': 'Уже есть в этом плейлисте',
        'unknown_track': 'Неизвестный трек',
    },
    'en': {
        'welcome': 'Hi, {name}! I am a music search and download bot.',
        'search_prompt': 'Send me a track or artist name, and I will find an MP3 file.',
        'open_app': '🎵 Open App',
        'choose_lang': 'Choose language / Выберите язык:',
        'lang_set_ru': '✅ Язык изменён на русский',
        'lang_set_en': '✅ Language set to English',
        'searching': '🔍 Searching: {query}',
        'downloading': '⬇️ Downloading...',
        'done': '✅ Done!',
        'not_found': '❌ Track not found.',
        'error': '⚠️ Error: {e}',
        'too_big': ' File is too big (>50 MB).',
        'add_to_playlist': '➕ To playlist',
        'select_playlist': 'Select a playlist',
        'create_playlist_first': 'First create a playlist: /new Name',
        'playlist_created': '✅ Playlist «{name}» created!',
        'playlist_exists': 'Playlist «{name}» already exists.',
        'usage_new': 'Usage: /new Name',
        'added_to_playlist': 'Added to «{name}»',
        'no_track': 'Download a track first!',
        'playlist_not_found': 'Playlist not found',
        'already_in_playlist': 'Already in this playlist',
        'unknown_track': 'Unknown track',
    }
}

user_languages = {}

def get_lang(user_id):
    return user_languages.get(user_id, 'ru')

def get_text(user_id, key, **kwargs):
    lang = get_lang(user_id)
    text = LANGUAGES[lang].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

# === ПОИСК И СКАЧИВАНИЕ ===
def search_spotify(query):
    try:
        results = sp.search(q=query, limit=1, type='track')
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            return f"{track['artists'][0]['name']} - {track['name']}"
    except Exception as e:
        print(f"Spotify error: {e}")
    return None

async def search_youtube_api(query):
    """Ищет видео через YouTube Data API v3"""
    if not YOUTUBE_API_KEY:
        print("⚠️ YOUTUBE_API_KEY не установлен!")
        return None
    
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&maxResults=1&q={quote(query)}&key={YOUTUBE_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('items') and len(data['items']) > 0:
                        video_id = data['items'][0]['id']['videoId']
                        title = data['items'][0]['snippet']['title']
                        print(f"✅ YouTube API нашёл: {title}")
                        return f"https://www.youtube.com/watch?v={video_id}"
                    else:
                        print(f"⚠️ YouTube API: items пустой для '{query}'")
                else:
                    error_text = await response.text()
                    print(f"❌ YouTube API error {response.status}: {error_text}")
    except Exception as e:
        print(f"❌ YouTube API exception: {e}")
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

# === ОБРАБОТЧИКИ КОМАНД ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Пользователь"
    
    # Клавиатура выбора языка
    lang_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="RU Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="GB English", callback_data="lang_en"),
        ]
    ])
    
    # Кнопка Mini App
    webapp_url = os.getenv("WEBAPP_URL", "https://music-finder-bot-2xi8.onrender.com")
    mini_app_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=get_text(user_id, 'open_app'), web_app=WebAppInfo(url=webapp_url))]],
        resize_keyboard=True
    )
    
    await message.answer(
        get_text(user_id, 'welcome', name=first_name) + "\n\n" +
        get_text(user_id, 'search_prompt') + "\n\n" +
        get_text(user_id, 'choose_lang'),
        reply_markup=lang_kb
    )
    
    await message.answer(
        " " + ("Открой Mini App для просмотра плейлистов:" if get_lang(user_id) == 'ru' else "Open Mini App to view playlists:"),
        reply_markup=mini_app_kb
    )

@dp.callback_query(lambda c: c.data.startswith('lang_'))
async def process_lang_choice(callback: types.CallbackQuery):
    lang = callback.data.split('_')[1]
    user_id = callback.from_user.id
    user_languages[user_id] = lang
    
    if lang == 'ru':
        await callback.message.edit_text(get_text(user_id, 'lang_set_ru'))
    else:
        await callback.message.edit_text(get_text(user_id, 'lang_set_en'))
    
    await callback.answer()

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    query = message.text
    status_msg = await message.answer(get_text(user_id, 'searching', query=query))
    
    spotify_name = search_spotify(query)
    yt_url = await search_youtube_api(spotify_name or query)
    
    if not yt_url:
        await status_msg.edit_text(get_text(user_id, 'not_found'))
        return
    
    await status_msg.edit_text(get_text(user_id, 'downloading'))
    
    try:
        filename = download_mp3(yt_url)
        last_track[user_id] = {"name": spotify_name or query}
        
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(get_text(user_id, 'too_big'))
            os.remove(filename)
            return

        pl_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=get_text(user_id, 'add_to_playlist'), callback_data="pl_menu")
        ]])
        
        await message.answer_audio(
            audio=types.FSInputFile(filename),
            caption=f"🎵 {spotify_name or query}",
            reply_markup=pl_kb
        )
        await status_msg.edit_text(get_text(user_id, 'done'))
        os.remove(filename)
    except Exception as e:
        await status_msg.edit_text(get_text(user_id, 'error', e=str(e)))

@dp.message(Command("new"))
async def cmd_new(message: types.Message):
    user_id = message.from_user.id
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(get_text(user_id, 'usage_new'))
        return
    name = parts[1].strip()
    data = load_playlists()
    uid = str(user_id)
    data.setdefault(uid, {})
    if name in data[uid]:
        await message.answer(get_text(user_id, 'playlist_exists', name=name))
        return
    data[uid][name] = []
    save_playlists(data)
    await message.answer(get_text(user_id, 'playlist_created', name=name))

@dp.callback_query(lambda c: c.data == "pl_menu")
async def pl_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = load_playlists()
    pls = data.get(str(user_id), {})
    if not pls:
        await callback.answer(get_text(user_id, 'create_playlist_first'), show_alert=True)
        return
    rows = [[InlineKeyboardButton(text=f"📁 {name}", callback_data=f"pl_add:{name}")] for name in pls.keys()]
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer(get_text(user_id, 'select_playlist'))

@dp.callback_query(lambda c: c.data.startswith("pl_add:"))
async def pl_add(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    name = callback.data.split(":", 1)[1]
    track_info = last_track.get(user_id)
    if not track_info:
        await callback.answer(get_text(user_id, 'no_track'), show_alert=True)
        return
    
    data = load_playlists()
    udata = data.setdefault(str(user_id), {})
    if name not in udata:
        await callback.answer(get_text(user_id, 'playlist_not_found'), show_alert=True)
        return
    
    track_name = track_info.get("name", get_text(user_id, 'unknown_track'))
    if any(t.get("name") == track_name for t in udata[name]):
        await callback.answer(get_text(user_id, 'already_in_playlist'), show_alert=True)
        return
    
    udata[name].append({"name": track_name})
    save_playlists(data)
    await callback.answer(get_text(user_id, 'added_to_playlist', name=name))

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