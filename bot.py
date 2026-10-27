import os
import yt_dlp
import asyncio
from youtube_search import YoutubeSearch
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.filters import Command
from aiohttp import ClientSession
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
from aiogram import Bot
import json
from aiogram.filters import CommandStart
from aiogram import F
import secrets
from aiogram.types import WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv
import os

# Установка команд меню
async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Главное меню"),
        BotCommand(command="help", description="📚 Справка по командам"),
        BotCommand(command="playlists", description="📁 Мои плейлисты"),
        BotCommand(command="new", description="➕ Создать плейлист"),
        BotCommand(command="show", description="👁 Открыть плейлист"),
        BotCommand(command="delete", description=" Удалить плейлист"),
        BotCommand(command="rename", description="✏️ Переименовать плейлист"),
        BotCommand(command="share", description="🔗 Поделиться плейлистом"),
        BotCommand(command="import", description=" Импортировать плейлист"),
    ]
    
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

# Загружаем переменные из файла .env
load_dotenv()

# ОТЛАДКА
print(f"🔍 Token loaded: {bool(os.getenv('TELEGRAM_BOT_TOKEN'))}")
print(f"🔍 Admin ID: {os.getenv('ADMIN_ID')}")

# === НАСТРОЙКИ (читаются из .env) ===
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOWNLOAD_DIR = "downloads/"

# ТЕЛЕГРАМ ID ДЛЯ УВЕДОМЛЕНИЯ
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Инициализация Spotify
sp = spotipy.Spotify(
    client_credentials_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

# Инициализация бота
dp = Dispatcher()

# Словарь с переводами
LANGUAGES = {
    'ru': {
        'welcome': 'Привет! Я бот для скачивания музыки.',
        'choose_lang': 'Выберите язык / Choose language:',
        'lang_set': '✅ Язык изменён на русский',
        'search_prompt': 'Отправьте мне название трека или исполнителя, и я найду и пришлю вам MP3 файл.',
        'example': 'Пример: Imagine Dragons Radioactive',
        'searching': '🔍 Ищу...',
        'downloading': '⬇️ Скачиваю...',
        'done': '✅ Готово!',
        'not_found': ' Не нашёл трек. Попробуйте другой запрос.',
        'error': '️ Ошибка при скачивании: {e}',
    },
    'en': {
        'welcome': 'Hi! I am a music download bot.',
        'choose_lang': 'Choose language / Выберите язык:',
        'lang_set': '✅ Language set to English',
        'search_prompt': 'Send me a track or artist name, and I will find and send you an MP3 file.',
        'example': 'Example: Imagine Dragons Radioactive',
        'searching': '🔍 Searching...',
        'downloading': '⬇️ Downloading...',
        'done': '✅ Done!',
        'not_found': '❌ Track not found. Try another query.',
        'error': '️ Download error: {e}',
    }
}

# Словарь для хранения языка каждого пользователя
user_languages = {}

def get_lang(user_id):
    """Получить язык пользователя (по умолчанию русский)"""
    return user_languages.get(user_id, 'ru')

def get_text(user_id, key):
    """Получить текст на языке пользователя"""
    lang = get_lang(user_id)
    return LANGUAGES[lang][key]

PLAYLISTS_FILE = "playlists.json"
last_track = {}

def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_playlists(data):
    with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

SHARED_PLAYLISTS_FILE = "shared_playlists.json"

def load_shared_playlists():
    if os.path.exists(SHARED_PLAYLISTS_FILE):
        with open(SHARED_PLAYLISTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_shared_playlists(data):
    with open(SHARED_PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def search_spotify(query):
    """Ищет трек в Spotify и возвращает точное название"""
    try:
        results = sp.search(q=query, limit=1, type='track')
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            artist = track['artists'][0]['name']
            title = track['name']
            return f"{artist} - {title}"
    except Exception as e:
        print(f"Ошибка Spotify: {e}")
    return None

def search_youtube(query):
    """Ищет видео на YouTube"""
    try:
        results = YoutubeSearch(query, max_results=1).to_dict()
        if results:
            video_id = results[0]['id']
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception as e:
        print(f"Ошибка YouTube: {e}")
    return None

def download_mp3(youtube_url, output_path=DOWNLOAD_DIR):
    """Скачивает MP3 и возвращает путь к файлу"""
    os.makedirs(output_path, exist_ok=True)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'outtmpl': f'{output_path}%(title)s.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'web_creator', 'android'],
            }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
    },
}
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
        return filename

@dp.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    username = message.from_user.username or "без_юзернейма"
    first_name = message.from_user.first_name or "Пользователь"

    with open("users_log.txt", "a", encoding="utf-8") as file:
        file.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | ID: {user_id} | @{username} | {first_name}\n")

            # Отправляем уведомление вам (только если это не вы сами)
    if user_id != ADMIN_ID:
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🆕 <b>Новый пользователь!</b>\n"
                f"👤 Имя: {first_name}\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"📱 Юзернейм: @{username}",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="RU Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="GB English", callback_data="lang_en"),
        ]
    ])
        # Кнопка Mini App
    webapp_url = "https://identity-fees-laws-fellow.trycloudflare.com"
    mini_app_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🎵 Открыть приложение", web_app=WebAppInfo(url=webapp_url))]],
        resize_keyboard=True
    )
    
    await message.answer(
        f"👋 Привет, {first_name}! Я бот для поиска и скачивания музыки.\n\n"
        "Отправьте мне название трека или исполнителя, и я найду MP3 файл.\n\n"
        "Выберите язык / Choose language:",
        reply_markup=keyboard
    )
    
    await message.answer(
        "🌐 Открой Mini App для просмотра плейлистов:",
        reply_markup=mini_app_kb
    )
    
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    # Сначала проверяем ручной выбор, потом язык Telegram, потом английский
    user_lang = user_languages.get(message.from_user.id, message.from_user.language_code or 'en')
    
    # ОТЛАДКА: выводим в терминал, какой язык определился
    print(f"🔍 Language code: {user_lang} | Full user info: {message.from_user.language_code}")
    
    if user_lang.startswith('ru'):
        help_text = (
            "📚 <b>Справка по командам бота</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎵 <b>Основные команды:</b>\n"
            "• Отправьте название трека или исполнителя — бот найдёт и пришлёт MP3\n"
            "• После скачивания нажмите «➕ В плейлист», чтобы сохранить трек\n\n"
            "📁 <b>Управление плейлистами:</b>\n"
            "• /new <i>Название</i> — создать новый плейлист\n"
            "• /playlists — список ваших плейлистов\n"
            "• /show <i>Название</i> — открыть плейлист с кнопками управления\n"
            "• /delete <i>Название</i> — удалить плейлист целиком\n"
            "• /rename <i>Старое Новое</i> — переименовать плейлист\n\n"
            "🔗 <b>Обмен плейлистами:</b>\n"
            "• /share <i>Название</i> — получить код для передачи плейлиста\n"
            "• /import <i>Код</i> — импортировать плейлист по коду\n"
            "• Кнопка «🔗 Поделиться» в плейлисте — быстрый способ получить код\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 <b>Советы:</b>\n"
            "• В плейлисте можно скачать любой трек кнопкой «⬇️ Скачать»\n"
            "• При импорте плейлист автоматически переименуется, если такое имя уже есть\n"
            "• Максимальный размер файла для скачивания — 50 МБ\n\n"
            "Если что-то не работает — напишите мне, и я помогу! 😊"
        )
    else:
        help_text = (
            "📚 <b>Bot Commands Help</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎵 <b>Music:</b>\n"
            "• Send a track name or artist — bot will find and send MP3\n"
            "• After downloading, tap «➕ To playlist» to save the track\n\n"
            "📁 <b>Playlists:</b>\n"
            "• /new <i>Name</i> — create a new playlist\n"
            "• /playlists — list your playlists\n"
            "• /show <i>Name</i> — open playlist with controls\n"
            "• /delete <i>Name</i> — delete playlist completely\n"
            "• /rename <i>Old New</i> — rename playlist\n\n"
            " <b>Sharing:</b>\n"
            "• /share <i>Name</i> — get a shareable code\n"
            "• /import <i>Code</i> — import a playlist by code\n"
            "• «🔗 Share» button in playlist — quick way to get the code\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "💡 <b>Tips:</b>\n"
            "• You can download any track from playlist with «⬇️ Download» button\n"
            "• On import, playlist will be auto-renamed if name already exists\n"
            "• Maximum file size for download — 50 MB\n\n"
            "If something doesn't work — write to me and I'll help! 😊"
        )
    
    await message.answer(help_text, parse_mode="HTML")

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "Выберите язык / Choose language:\n\n"
            "• /lang ru — Русский\n"
            "• /lang en — English",
            parse_mode="HTML"
        )
        return
    
    lang = parts[1].strip().lower()
    
    if lang not in ['ru', 'en']:
        await message.answer("Неподдерживаемый язык. Используйте 'ru' или 'en'.")
        return
    
    user_languages[message.from_user.id] = lang
    
    if lang == 'ru':
        await message.answer("✅ Язык изменён на русский")
    else:
        await message.answer("✅ Language changed to English")

@dp.callback_query(lambda c: c.data.startswith('lang_'))
async def process_lang_choice(callback: types.CallbackQuery):
    lang = callback.data.split('_')[1]
    user_id = callback.from_user.id
    user_languages[user_id] = lang
    
    await callback.message.edit_text(
        get_text(user_id, 'lang_set') + '\n\n' + 
        get_text(user_id, 'search_prompt')  
    )

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_message(message: types.Message):
    
    """Обработка текстовых сообщений"""
    query = message.text
    
    # Отправляем сообщение о поиске
    status_msg = await message.answer(f" Ищу: {query}")
    
    # 1. Ищем в Spotify для точного названия
    spotify_name = search_spotify(query)
    if spotify_name:
        await status_msg.edit_text(f" Найдено в Spotify: {spotify_name}\n Ищу на YouTube...")
        search_query = spotify_name
    else:
        await status_msg.edit_text(f" Не найдено в Spotify, ищу на YouTube по вашему запросу...\n")
        search_query = query
    
    # 2. Ищем на YouTube
    yt_url = search_youtube(search_query)
    if not yt_url:
        await status_msg.edit_text(" Трек не найден на YouTube.")
        return
    
    await status_msg.edit_text(f" Найдено: {yt_url}\n Скачиваю...")
    
    # 3. Скачиваем
    try:
        filename = download_mp3(yt_url)
        
        # 4. Отправляем файл
        cover_url = ""
        try:
            info = yt_dlp.YoutubeDL({'quiet': True}).extract_info(yt_url, download=False)
            if info and 'thumbnail' in info:
                cover_url = info['thumbnail']
        except:
            pass
        
        last_track[message.from_user.id] = {
            "name": spotify_name or query,
            "cover_url": cover_url
        }
        pl_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ В плейлист", callback_data="pl_menu")]
        ])

        # Проверяем размер файла (лимит Telegram — 50 МБ)
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(f"❌ Файл слишком большой ({file_size // 1024 // 1024} МБ). Максимум 50 МБ.")
            os.remove(filename)
            return

        await message.answer_audio(
            audio=types.FSInputFile(filename),
            caption=f"🎵 {spotify_name or query}",
            parse_mode="Markdown",
            reply_markup=pl_kb
        )
        
        await status_msg.edit_text(" Готово!")
        
        # Удаляем скачанный файл (чтобы не занимал место)
        os.remove(filename)
        
    except Exception as e:
        await status_msg.edit_text(f" Ошибка при скачивании: {e}")

# === КОМАНДЫ ПЛЕЙЛИСТОВ ===
@dp.message(Command("playlists"))
async def cmd_playlists(message: types.Message):
    data = load_playlists()
    tracks = data.get(str(message.from_user.id), {})
    
    if not tracks:
        await message.answer(" У вас пока нет плейлистов. Создайте первый командой /new Название")
        return
    
    # Формируем текст
    text = "📁 <b>Ваши плейлисты:</b>\n\n"
    for name, playlist in tracks.items():
        text += f"📂 <b>{name}</b> — {len(playlist)} тр.\n"
    
    # Формируем кнопки
    keyboard_rows = []
    for name in tracks.keys():
        callback_data = f"pl_show:{name}"
        # Проверяем длину callback_data (лимит Telegram 64 байта)
        if len(callback_data.encode("utf-8")) <= 64:
            keyboard_rows.append([
                InlineKeyboardButton(text=f"📂 {name}", callback_data=callback_data)
            ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(lambda c: c.data.startswith("pl_show:"))
async def pl_show_callback(callback: types.CallbackQuery):
    name = callback.data.split(":", 1)[1]
    
    data = load_playlists()
    tracks = data.get(str(callback.from_user.id), {}).get(name)
    
    if tracks is None:
        await callback.answer(f"Плейлист «{name}» не найден", show_alert=True)
        return
    
    if not tracks:
        await callback.answer(f"Плейлист «{name}» пуст", show_alert=True)
        return
    
    # Формируем текст
    text = f"🎵 <b>Плейлист: {name}</b>\n"
    text += f"📊 Треков: {len(tracks)}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, track in enumerate(tracks, 1):
        track_name = track.get("name", "Неизвестный трек")
        text += f"{i}.  <b>{track_name}</b>\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━"
    
    # Формируем кнопки
    keyboard_rows = []
    for i, track in enumerate(tracks, 1):
        download_cb = f"pl_download:{name}:{i-1}"
        delete_cb = f"pl_delete:{name}:{i-1}"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"⬇️ Скачать {i}", callback_data=download_cb),
            InlineKeyboardButton(text=f" Удалить {i}", callback_data=delete_cb)
        ])
    
    # Кнопка "Поделиться"
    share_cb = f"pl_share:{name}"
    if len(share_cb.encode("utf-8")) <= 64:
        keyboard_rows.append([
            InlineKeyboardButton(text=" Поделиться", callback_data=share_cb)
        ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    # Отправляем с обложкой
    last_cover = tracks[-1].get("cover_url", "")
    if last_cover and last_cover.startswith("http"):
        try:
            await callback.message.answer_photo(
                photo=last_cover,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception as e:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
            print(f"⚠️ Не удалось отправить обложку: {e}")
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    
    await callback.answer()

@dp.message(Command("new"))
async def cmd_new(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /new НазваниеПлейлиста")
        return
    name = parts[1].strip()
    if not name or "\n" in name:
        await message.answer("Название не может быть пустым и не должно содержать перенос строки.")
        return
    if len(name.encode("utf-8")) > 50:
        await message.answer("Слишком длинное название, сделайте короче (до ~25 символов).")
        return
    data = load_playlists()
    uid = str(message.from_user.id)
    data.setdefault(uid, {})
    if name in data[uid]:
        await message.answer(f"Плейлист «{name}» уже существует.")
        return
    data[uid][name] = []
    save_playlists(data)
    await message.answer(f"✅ Плейлист «{name}» создан! Теперь скачайте трек и нажмите «➕ В плейлист».")

@dp.callback_query(lambda c: c.data == "pl_menu")
async def pl_menu(callback: types.CallbackQuery):
    data = load_playlists()
    pls = data.get(str(callback.from_user.id), {})
    if not pls:
        await callback.answer("Сначала создайте плейлист: /new Название", show_alert=True)
        return
    rows = []
    row = []
    for name in pls.keys():
        cb = f"pl_add:{name}"
        if len(cb.encode("utf-8")) > 64:
            continue
        row.append(InlineKeyboardButton(text=f"📁 {name}", callback_data=cb))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("Выберите плейлист")

@dp.callback_query(lambda c: c.data.startswith("pl_add:"))
async def pl_add(callback: types.CallbackQuery):
    name = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    track_info = last_track.get(uid)
    if not track_info:
        await callback.answer("Нет трека для добавления (скачайте заново)", show_alert=True)
        return
    
    track_name = track_info.get("name", "Неизвестный трек")
    cover_url = track_info.get("cover_url", "")
    
    data = load_playlists()
    udata = data.setdefault(str(uid), {})
    if name not in udata:
        await callback.answer("Такого плейлиста больше нет", show_alert=True)
        return
    
    for t in udata[name]:
        if t.get("name") == track_name:
            await callback.answer("Уже есть в этом плейлисте", show_alert=True)
            return
    
    udata[name].append({"name": track_name, "cover_url": cover_url})
    save_playlists(data)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"Добавлено в «{name}»")
    await callback.message.answer(f"✅ Трек «{track_name}» добавлен в плейлист «{name}» ({len(udata[name])} тр.)")

@dp.message(Command("show"))
async def cmd_show(message: types.Message, name: str = None):
    if name is None:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.answer("Использование: /show НазваниеПлейлиста")
            return
        name = parts[1].strip()
    data = load_playlists()
    tracks = data.get(str(message.from_user.id), {}).get(name)
    if tracks is None:
        await message.answer(f"❌ Плейлист «{name}» не найден.")
        return
    if not tracks:
        await message.answer(f"📭 Плейлист «{name}» пуст.")
        return
    
    text = f"🎵 <b>Плейлист: {name}</b>\n"
    text += f"📊 Треков: {len(tracks)}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for i, track in enumerate(tracks, 1):
        track_name = track.get("name", "Неизвестный трек")
        text += f"{i}. 🎧 <b>{track_name}</b>\n"
    
    text += "━━━━━━━━━━━━━━━━━━━━"
    
    keyboard_rows = []
    for i, track in enumerate(tracks, 1):
        download_cb = f"pl_download:{name}:{i-1}"
        delete_cb = f"pl_delete:{name}:{i-1}"
        keyboard_rows.append([
            InlineKeyboardButton(text=f"⬇️ Скачать {i}", callback_data=download_cb),
            InlineKeyboardButton(text=f"🗑 Удалить {i}", callback_data=delete_cb)
        ])

    # Кнопка "Поделиться" — отдельной строкой внизу
    share_cb = f"pl_share:{name}"
    if len(share_cb.encode("utf-8")) <= 64:
        keyboard_rows.append([
            InlineKeyboardButton(text="🔗 Поделиться", callback_data=share_cb)
        ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    
    last_cover = tracks[-1].get("cover_url", "")
    if last_cover and last_cover.startswith("http"):
        try:
            await message.answer_photo(
                photo=last_cover,
                caption=text,
                parse_mode="HTML",
                reply_markup=kb
            )
        except Exception as e:
            await message.answer(text, parse_mode="HTML", reply_markup=kb)
            print(f"⚠️ Не удалось отправить обложку: {e}")
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /delete НазваниеПлейлиста")
        return
    name = parts[1].strip()
    data = load_playlists()
    uid = str(message.from_user.id)
    user_data = data.get(uid, {})
    
    if name not in user_data:
        await message.answer(f"❌ Плейлист «{name}» не найден.")
        return
    
    del user_data[name]
    save_playlists(data)
    await message.answer(f"🗑 Плейлист «{name}» полностью удалён.")

@dp.message(Command("rename"))
async def cmd_rename(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Использование: /rename СтароеНазвание НовоеНазвание")
        return
    
    data = load_playlists()
    uid = str(message.from_user.id)
    user_data = data.get(uid, {})
    user_playlists = list(user_data.keys())
    
    if not user_playlists:
        await message.answer("У вас нет плейлистов для переименования.")
        return
    
    # Получаем всё после /rename
    full_text = message.text.split(maxsplit=1)[1]
    
    # Пытаемся найти старое название среди плейлистов пользователя
    old_name = None
    new_name = None
    
    # Сортируем по длине (сначала длинные названия), чтобы найти точное совпадение
    sorted_playlists = sorted(user_playlists, key=len, reverse=True)
    
    for pl_name in sorted_playlists:
        if full_text.startswith(pl_name):
            old_name = pl_name
            # Всё что после старого названия — это новое название
            remainder = full_text[len(old_name):].strip()
            if remainder:
                new_name = remainder
            break
    
    if not old_name:
        await message.answer(f"❌ Плейлист не найден. Ваши плейлисты: {', '.join(user_playlists)}")
        return
    
    if not new_name:
        await message.answer("Укажите новое название после старого.")
        return
    
    # Проверки нового названия
    if "\n" in new_name:
        await message.answer("Название не должно содержать перенос строки.")
        return
        
    if len(new_name.encode("utf-8")) > 50:
        await message.answer("Слишком длинное новое название (максимум ~25 символов).")
        return
        
    if new_name in user_data:
        await message.answer(f"⚠️ Плейлист «{new_name}» уже существует.")
        return
        
    # Переименовываем
    user_data[new_name] = user_data.pop(old_name)
    save_playlists(data)
    
    await message.answer(f"✅ Плейлист «{old_name}» переименован в «{new_name}».")

@dp.message(Command("share"))
async def cmd_share(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /share НазваниеПлейлиста")
        return
    name = parts[1].strip()
    
    data = load_playlists()
    uid = str(message.from_user.id)
    user_data = data.get(uid, {})
    
    if name not in user_data:
        await message.answer(f"❌ Плейлист «{name}» не найден.")
        return
    
    tracks = user_data[name]
    if not tracks:
        await message.answer(f"📭 Плейлист «{name}» пуст. Добавьте хотя бы один трек.")
        return
    
    # Генерируем короткий код (6 символов)
    code = secrets.token_urlsafe(4)[:6]
    
    # Сохраняем в общие плейлисты
    shared = load_shared_playlists()
    shared[code] = {
        "name": name,
        "author": message.from_user.first_name or "Аноним",
        "tracks": tracks
    }
    save_shared_playlists(shared)
    
    await message.answer(
        f" Плейлист «{name}» готов к передаче!\n\n"
        f"📋 <b>Код:</b> <code>{code}</code>\n"
        f"📊 Треков: {len(tracks)}\n\n"
        f"Отправьте этот код другу, чтобы он мог импортировать плейлист командой:\n"
        f"/import {code}",
        parse_mode="HTML"
    )


@dp.message(Command("import"))
async def cmd_import(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Использование: /import КодПлейлиста")
        return
    code = parts[1].strip()
    
    shared = load_shared_playlists()
    if code not in shared:
        await message.answer("❌ Плейлист с таким кодом не найден. Проверьте правильность кода.")
        return
    
    pl_info = shared[code]
    pl_name = pl_info["name"]
    tracks = pl_info["tracks"]
    author = pl_info.get("author", "Неизвестно")
    
    # Добавляем плейлист пользователю
    data = load_playlists()
    uid = str(message.from_user.id)
    user_data = data.setdefault(uid, {})
    
    # Если плейлист с таким именем уже есть — добавляем "_копия"
    original_name = pl_name
    counter = 1
    while pl_name in user_data:
        pl_name = f"{original_name}_копия{counter}"
        counter += 1
    
    user_data[pl_name] = tracks.copy()
    save_playlists(data)
    
    await message.answer(
        f"✅ Плейлист успешно импортирован!\n\n"
        f"📁 <b>Название:</b> {pl_name}\n"
        f"👤 <b>Автор:</b> {author}\n"
        f" <b>Треков:</b> {len(tracks)}\n\n"
        f"Используйте /show {pl_name} чтобы открыть плейлист.",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("pl_share:"))
async def pl_share(callback: types.CallbackQuery):
    name = callback.data.split(":", 1)[1]
    uid = callback.from_user.id
    
    data = load_playlists()
    user_data = data.get(str(uid), {})
    
    if name not in user_data:
        await callback.answer("Плейлист не найден", show_alert=True)
        return
    
    tracks = user_data[name]
    if not tracks:
        await callback.answer("Плейлист пуст", show_alert=True)
        return
    
    # Генерируем короткий код
    code = secrets.token_urlsafe(4)[:6]
    
    # Сохраняем в общие плейлисты
    shared = load_shared_playlists()
    shared[code] = {
        "name": name,
        "author": callback.from_user.first_name or "Аноним",
        "tracks": tracks
    }
    save_shared_playlists(shared)
    
    await callback.answer("✅ Код создан!")
    await callback.message.answer(
        f"🔗 Плейлист «{name}» готов к передаче!\n\n"
        f"📋 <b>Код:</b> <code>{code}</code>\n"
        f"📊 Треков: {len(tracks)}\n\n"
        f"Отправьте этот код другу:\n/import {code}",
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data.startswith("pl_download:"))
async def pl_download(callback: types.CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    playlist_name = parts[1]
    track_index = int(parts[2])
    
    data = load_playlists()
    tracks = data.get(str(callback.from_user.id), {}).get(playlist_name, [])
    if track_index >= len(tracks):
        await callback.answer("Трек не найден", show_alert=True)
        return
    
    track_info = tracks[track_index]
    track_name = track_info.get("name", "")
    
    if not track_name:
        await callback.answer("Название трека не найдено", show_alert=True)
        return
    
    await callback.answer(f"Скачиваю: {track_name}")
    await callback.message.answer(f"️ Ищу: {track_name}...")
    
    # Ищем на YouTube
    yt_url = search_youtube(track_name)
    if not yt_url:
        await callback.message.answer("❌ Трек не найден на YouTube.")
        return
    
    # Скачиваем
    try:
        filename = download_mp3(yt_url)
        
        # Проверяем размер
        file_size = os.path.getsize(filename)
        if file_size > 50 * 1024 * 1024:
            await callback.message.answer(f"❌ Файл слишком большой ({file_size // 1024 // 1024} МБ). Максимум 50 МБ.")
            os.remove(filename)
            return
        
        # Отправляем файл
        await callback.message.answer_audio(
            audio=types.FSInputFile(filename),
            caption=f"🎵 {track_name}",
            parse_mode="Markdown"
        )
        
        await callback.message.answer("✅ Готово!")
        os.remove(filename)
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка при скачивании: {e}")

@dp.callback_query(lambda c: c.data.startswith("pl_delete:"))
async def pl_delete(callback: types.CallbackQuery):
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer("Ошибка", show_alert=True)
        return
    playlist_name = parts[1]
    track_index = int(parts[2])
    
    data = load_playlists()
    uid = str(callback.from_user.id)
    tracks = data.get(uid, {}).get(playlist_name, [])
    if track_index >= len(tracks):
        await callback.answer("Трек не найден", show_alert=True)
        return
    
    track_name = tracks[track_index].get("name", "")
    tracks.pop(track_index)
    save_playlists(data)
    await callback.answer(f"Удалено: {track_name}")
    await callback.message.answer(f"🗑 Трек «{track_name}» удалён из плейлиста «{playlist_name}»")

async def main():
    """Запуск бота"""
    
    # Создаем бота (работает через Happ VPN)
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    # Устанавливаем команды меню
    await set_commands(bot)
    
    print("✅ Бот запущен! Нажмите Ctrl+C для остановки.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())