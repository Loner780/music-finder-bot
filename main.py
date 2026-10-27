import os
import yt_dlp
from youtube_search import YoutubeSearch

def search_and_download(query):
    print(f" Ищем: {query}")
    
    # Ищем на YouTube
    results = YoutubeSearch(query, max_results=1).to_dict()
    if not results:
        print(" Ничего не найдено")
        return
    
    #  только ID видео, без параметров плейлиста
    video_id = results[0]['id']
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f" Найдено: {url}")

    # Скачиваем MP3
    os.makedirs("downloads", exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'quiet': True,
        'js_runtimes': {'deno': {}},
        'noplaylist': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(" Готово! Файл в папке downloads/")

if __name__ == "__main__":
    query = input("Введите название трека: ")
    search_and_download(query)