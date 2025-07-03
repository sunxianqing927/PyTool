import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import json
import time
import socket
import pysrt
import webvtt

# === 设置 ===
MPV_SOCKET_PATH = r"\\.\pipe\mpvsocket"
video_path = ""
subtitle_path = ""
subtitles = []  # [(start_seconds, end_seconds, text), ...]
current_index = 0
paused = False

# === 自动查找字幕（根据视频文件名） ===
def auto_find_subtitle():
    global subtitle_path
    if not video_path:
        return
    base = os.path.splitext(video_path)[0]
    srt = base + ".en.srt"
    vtt = base + ".en.vtt"
    if os.path.exists(srt):
        subtitle_path = srt
    elif os.path.exists(vtt):
        subtitle_path = vtt
    else:
        print("未检测到对应字幕文件 (.en.srt 或 .en.vtt)，请点击【加载字幕文件】手动选择。")
        return
    subtitle_label.config(text=f"字幕: {os.path.basename(subtitle_path)}")
    load_subtitles()

# === 载入字幕（支持 .srt 和 .vtt） ===
def load_subtitles():
    global subtitles
    if not os.path.exists(subtitle_path):
        messagebox.showerror("错误", "字幕文件未找到！")
        return []

    try:
        if subtitle_path.lower().endswith('.srt'):
            subs = pysrt.open(subtitle_path)
            subtitles = [(sub.start.hours * 3600 + sub.start.minutes * 60 + sub.start.seconds + sub.start.milliseconds / 1000,
                          sub.end.hours * 3600 + sub.end.minutes * 60 + sub.end.seconds + sub.end.milliseconds / 1000,
                          sub.text.strip().replace('\n', ' ')) for sub in subs]

        elif subtitle_path.lower().endswith('.vtt'):
            subs = webvtt.read(subtitle_path)
            subtitles = []
            for caption in subs:
                h1, m1, s1 = caption.start.split(':')
                s1, ms1 = s1.split('.')
                start_sec = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000

                h2, m2, s2 = caption.end.split(':')
                s2, ms2 = s2.split('.')
                end_sec = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000

                subtitles.append((start_sec, end_sec, caption.text.strip().replace('\n', ' ')))
        else:
            messagebox.showerror("错误", "仅支持 .srt 和 .vtt 格式字幕")
            subtitles = []
            return []

        return subtitles

    except Exception as e:
        messagebox.showerror("字幕解析错误", str(e))
        subtitles = []
        return []

# === 选择视频文件 ===
def select_video():
    global video_path
    path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4;*.mkv;*.avi"), ("所有文件", "*.*")])
    if path:
        video_path = path
        video_label.config(text=f"视频: {os.path.basename(path)}")
        auto_find_subtitle()

# === 选择字幕文件 ===
def select_subtitle():
    global subtitle_path
    path = filedialog.askopenfilename(filetypes=[("字幕文件", "*.srt;*.vtt"), ("所有文件", "*.*")])
    if path:
        subtitle_path = path
        subtitle_label.config(text=f"字幕: {os.path.basename(path)}")
        load_subtitles()

# === 启动 mpv 播放器 ===
def start_mpv():
    global paused, current_index
    if not os.path.exists(video_path):
        messagebox.showerror("错误", "未找到视频文件！")
        return

    try:
        skip_count = 0
        try:
            skip_count = int(skip_entry.get())
        except:
            pass
        current_index = skip_count

        subprocess.Popen([
            "mpv", video_path,
            f"--input-ipc-server={MPV_SOCKET_PATH}"
        ])
        time.sleep(1)
        paused = False
        threading.Thread(target=auto_repeat_all, daemon=True).start()
    except Exception as e:
        messagebox.showerror("启动失败", f"无法启动 mpv：{e}")

# === 播放/暂停切换 ===
def toggle_pause():
    global paused
    paused = not paused
    toggle_button.config(text="继续播放" if paused else "暂停播放")

# === mpv 跳转函数 ===
def seek_to(seconds):
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {
                "command": ["set_property", "time-pos", seconds]
            }
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        messagebox.showerror("通信错误", f"无法连接 mpv：{e}")

# === 自动复读所有句子 ===
def auto_repeat_all():
    global current_index
    try:
        repeat_count = int(repeat_entry.get())
    except:
        repeat_count = 3
    while current_index < len(subtitles):
        if paused:
            time.sleep(0.1)
            continue
        start_sec, end_sec, text = subtitles[current_index]
        duration = end_sec - start_sec
        for _ in range(repeat_count):
            if paused:
                break
            seek_to(start_sec)
            time.sleep(duration)
        current_index += 1

# === 创建GUI ===
root = tk.Tk()
root.title("Subtitle Repeater (Simple Repeat Mode)")

tk.Button(root, text="选择视频文件", command=select_video).pack(pady=5)
video_label = tk.Label(root, text="视频: 未选择")
video_label.pack()

tk.Button(root, text="选择字幕文件 (.srt 或 .vtt)", command=select_subtitle).pack(pady=5)
subtitle_label = tk.Label(root, text="字幕: 未选择")
subtitle_label.pack()

tk.Label(root, text="复读次数:").pack()
repeat_entry = tk.Entry(root, width=5)
repeat_entry.insert(0, "3")
repeat_entry.pack()

tk.Label(root, text="跳过前几句:").pack()
skip_entry = tk.Entry(root, width=5)
skip_entry.insert(0, "0")
skip_entry.pack()

tk.Button(root, text="启动 mpv 播放器并开始复读", command=start_mpv).pack(pady=10)
toggle_button = tk.Button(root, text="暂停播放", command=toggle_pause)
toggle_button.pack(pady=5)

root.mainloop()
