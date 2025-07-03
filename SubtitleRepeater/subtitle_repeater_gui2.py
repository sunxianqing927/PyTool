import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import json
import time
import socket

# === 设置 ===
MPV_SOCKET_PATH = r"\\.\pipe\mpvsocket"
video_path = ""
paused = False

# === 选择视频文件 ===
def select_video():
    global video_path
    path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4;*.mkv;*.avi"), ("所有文件", "*.*")])
    if path:
        video_path = path
        video_label.config(text=f"视频: {os.path.basename(path)}")

# === 启动 mpv 播放器 ===
def start_mpv():
    global paused
    if not os.path.exists(video_path):
        messagebox.showerror("错误", "未找到视频文件！")
        return

    try:
        subprocess.Popen([
            "mpv", video_path,
            f"--input-ipc-server={MPV_SOCKET_PATH}"
        ])
        time.sleep(1)
        paused = False
        threading.Thread(target=manual_repeat_mode, daemon=True).start()
    except Exception as e:
        messagebox.showerror("启动失败", f"无法启动 mpv：{e}")

# === 播放/暂停切换 ===
def toggle_pause():
    global paused
    paused = not paused
    if paused:
        pause_mpv()
        toggle_button.config(text="继续播放")
    else:
        resume_mpv()
        toggle_button.config(text="暂停播放")

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

# === 暂停视频播放 ===
def pause_mpv():
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {
                "command": ["set_property", "pause", True]
            }
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"暂停失败: {e}")

# === 恢复视频播放 ===
def resume_mpv():
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {
                "command": ["set_property", "pause", False]
            }
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"恢复播放失败: {e}")

# === 手动时间段复读模式 ===
def manual_repeat_mode():
    try:
        repeat_count = int(repeat_entry.get())
    except:
        repeat_count = 3
    try:
        delay = float(delay_entry.get())
    except:
        delay = 1.5
    try:
        duration = float(duration_entry.get())
    except:
        duration = 20.0

    start_time = 0
    while True:
        if paused:
            time.sleep(0.1)
            continue
        for _ in range(repeat_count):
            if paused:
                break
            seek_to(start_time)
            resume_mpv()
            time.sleep(duration)
            pause_mpv()
            time.sleep(delay)
        start_time += duration

# === 创建GUI ===
root = tk.Tk()
root.title("Fixed Time Repeater")

tk.Button(root, text="选择视频文件", command=select_video).pack(pady=5)
video_label = tk.Label(root, text="视频: 未选择")
video_label.pack()

tk.Label(root, text="复读时长（秒）:").pack()
duration_entry = tk.Entry(root, width=5)
duration_entry.insert(0, "60.0")
duration_entry.pack()

tk.Label(root, text="复读次数:").pack()
repeat_entry = tk.Entry(root, width=5)
repeat_entry.insert(0, "3")
repeat_entry.pack()

tk.Label(root, text="复读间隔时间（秒）:").pack()
delay_entry = tk.Entry(root, width=5)
delay_entry.insert(0, "1.5")
delay_entry.pack()

tk.Button(root, text="启动 mpv 播放器并开始复读", command=start_mpv).pack(pady=10)
toggle_button = tk.Button(root, text="暂停播放", command=toggle_pause)
toggle_button.pack(pady=5)

root.mainloop()
