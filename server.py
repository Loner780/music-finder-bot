from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Создаем приложение FastAPI
app = FastAPI(title="Music Finder Mini App Server")

# 1. Настраиваем CORS, чтобы Telegram мог открывать этот сайт
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем запросы отовсюду (для Telegram это ок)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Указываем путь к папке mini_app
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "mini_app"

# 3. Монтируем папку со статикой (чтобы работали CSS, JS, картинки)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 4. Главная страница: отдаем файл index.html
@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    
    return HTMLResponse(
        "<h1>Mini App не найден!</h1><p>Убедись, что файл index.html лежит в папке mini_app/</p>", 
        status_code=404
    )

# 5. Простая проверка, что сервер жив
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Server is running!"}