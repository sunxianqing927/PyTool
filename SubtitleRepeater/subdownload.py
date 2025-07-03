import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

SHOW_NAME = "Rick and Morty"
SEASONS = 7
EPISODES = 12
MAX_WORKERS = 7  # 同时运行的字幕下载任务数

def download_subtitle(season, episode):
    filename = f"{SHOW_NAME}.S{season:02d}E{episode:02d}.mp4"
    print(f"🎬 下载字幕: {filename}")
    try:
        subprocess.run(["subliminal", "download", "-l", "en", filename], check=True)
    except subprocess.CalledProcessError:
        print(f"❌ 失败: {filename}")

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    for season in range(1, SEASONS + 1):
        for episode in range(1, EPISODES + 1):
            executor.submit(download_subtitle, season, episode)
