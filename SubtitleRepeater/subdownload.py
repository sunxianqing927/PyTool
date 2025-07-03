import os
import subprocess

SHOW_NAME = "Silicon.Valley"
SEASONS = 6    # 改为你想下载的总季数
EPISODES = 10  # 每季集数

for season in range(1, SEASONS + 1):
    for episode in range(1, EPISODES + 1):
        fake_filename = f"{SHOW_NAME}.S{season:02d}E{episode:02d}.mp4"
        print(f"🎬 下载字幕: {fake_filename}")
        try:
            subprocess.run(["subliminal", "download", "-l", "en", fake_filename], check=True)
        except subprocess.CalledProcessError:
            print(f"❌ 失败: {fake_filename}")
