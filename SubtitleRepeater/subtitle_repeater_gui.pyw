import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import json
import time
import pysrt
import datetime
import threading
import keyboard  # 全局键盘监听
from tkinter import font
import pygetwindow as gw
import tkinter.font as tkfont


# === 原子变量类 ===
class AtomicInteger:
    def __init__(self, value=0):
        self._value = value
        self._lock = threading.Lock()

    def get(self):
        with self._lock:
            return self._value

    def set(self, value):
        with self._lock:
            self._value = value

    def increment(self):
        with self._lock:
            self._value += 1
            return self._value

    def decrement(self):
        with self._lock:
            self._value -= 1
            return self._value


def save_params(filepath, **kwargs):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(kwargs, f, ensure_ascii=False, indent=2)


def load_params(filepath, namespace=None):
    if not os.path.exists(filepath):
        print(f"⚠️ 文件不存在：{filepath}，返回空参数")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        params = json.load(f)

    # 默认写入调用者的全局变量环境
    if namespace is None:
        namespace = globals()

    for key, value in params.items():
        namespace[key] = value


# === 全局变量 ===
MPV_SOCKET_PATH = rf"\\.\pipe\mpvsocket_{os.getpid()}"
video_path = ""
subtitle_path = ""
subtitles = []
subtitles_sub2 = []
g_current_index = AtomicInteger(0)
paused = False
close_mpv = False  # 用于控制 mpv 播放器的关闭

f_current_index = 0
f_show_subtitle = True
f_fullscreen = False
f_subtitle_offset = False
f_subtitle_ch_first = False
f_repeat_entry = "5"
f_repeat_intrval_entry = "5"
f_continue_entry = "5"
f_pause_entry = "5"
f_subtitles_entry = "10"
f_speed_slider = 1.0

load_params("params.json")

g_current_index.set(f_current_index)  # 设置初始索引


# === 自动查找字幕 ===
def auto_find_subtitle():
    global subtitle_path
    if not video_path:
        return
    base = os.path.splitext(video_path)[0]
    for ext in [".srt"]:
        test_path = base + ext
        if os.path.exists(test_path):
            subtitle_path = test_path
            break
    else:
        print("未检测到字幕文件")
        return
    subtitle_label.config(text=f"字幕: {os.path.basename(subtitle_path)}")
    load_subtitles()
    update_progress_controls()


# === 加载字幕 ===
def load_subtitles():
    global subtitles, subtitles_sub2
    if not os.path.exists(subtitle_path):
        messagebox.showerror("错误", "字幕文件未找到！")
        return []

    try:
        if subtitle_path.lower().endswith(".srt"):
            subs = pysrt.open(subtitle_path)
            subtitles = [
                (
                    sub.start.ordinal / 1000,
                    sub.end.ordinal / 1000,
                    sub.text.strip(),
                )
                for sub in subs
            ]

            subtitles_sub2 = None
            new_path = subtitle_path[:-4] + "_sub2.srt"  # 去掉最后的 .str 再拼接
            if os.path.exists(new_path):
                subs = pysrt.open(new_path)
                subtitles_sub2 = [
                    (
                        sub.start.ordinal / 1000,
                        sub.end.ordinal / 1000,
                        sub.text.strip(),
                    )
                    for sub in subs
                ]

                if len(subtitles_sub2) != len(subtitles):
                    subtitles_sub2 = None
        else:
            messagebox.showerror("错误", "不支持的字幕格式！")
            subtitles = []
            return []

        subtitles.append(subtitles[-1])
        return subtitles

    except Exception as e:
        messagebox.showerror("字幕解析错误", str(e))
        subtitles = []
        return []


def update_video():
    video_label.config(text=f"视频: {os.path.basename(video_path)}")
    auto_find_subtitle()
    update_progress_controls()


# === 文件选择 ===
def select_video():
    global video_path
    path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4;*.mkv;*.avi"), ("所有文件", "*.*")])
    if path:
        video_path = path
        g_current_index.set(0)
        update_video()


def select_subtitle():
    global subtitle_path
    path = filedialog.askopenfilename(filetypes=[("字幕文件", "*.srt"), ("所有文件", "*.*")])
    if path:
        subtitle_path = path
        subtitle_label.config(text=f"字幕: {os.path.basename(path)}")
        load_subtitles()
        update_progress_controls()


def set_fullscreen(state=True):
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "fullscreen", state]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"设置全屏失败: {e}")


# 将秒转为 SRT 时间格式
def seconds_to_srt_timestamp(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


# === 字幕显示窗口 ===
subtitle_display_window = None
subtitle_text = None


def on_close_subtitle_display_window():
    global subtitle_display_window
    subtitle_display_window.destroy()
    subtitle_display_window = None


def show_subtitle_window():
    global subtitle_display_window, subtitle_text
    if subtitle_display_window:
        return  # 避免重复创建
    subtitle_display_window = tk.Toplevel(root)
    subtitle_display_window.title("字幕显示")
    subtitle_display_window.configure(bg="black")
    subtitle_display_window.geometry("470x1000+1450+0")
    subtitle_display_window.protocol("WM_DELETE_WINDOW", on_close_subtitle_display_window)

    subtitle_display_window.bind("<Unmap>", minimize_other)  # 最小化时触发
    subtitle_display_window.bind("<Map>", restore_other)
    subtitle_display_window.bind("<FocusIn>", on_focus_in)

    subtitle_display_window.bind("<Left>", lambda event: on_prev())
    subtitle_display_window.bind("<Control-Left>", lambda event: on_prev(True))
    subtitle_display_window.bind("<Right>", lambda event: on_next())
    subtitle_display_window.bind("<Control-Right>", lambda event: on_next(True))
    subtitle_display_window.bind("<space>", lambda event: toggle_pause2())

    # 获取默认字体并修改大小
    default_font = tkfont.nametofont("TkDefaultFont").copy()
    default_font.configure(size=16)  # 修改字体大小 设置你想要的大小，比如 16

    # 应用于 Text 控件
    subtitle_text = tk.Text(subtitle_display_window, wrap="word", bg="#d3d3d3", font=default_font)
    subtitle_text.pack(fill="both", expand=True)
    # 字体设置
    bold_font = font.Font(subtitle_text, subtitle_text.cget("font"))
    bold_font.configure(weight="bold")

    # 中间行（主字幕）样式
    subtitle_text.tag_configure("center", font=bold_font, foreground="#204080")
    # 上下行（弱化字幕）样式
    subtitle_text.tag_configure("faded", font=bold_font)


# === 启动播放 ===
def start_mpv():
    global paused
    if not os.path.exists(video_path):
        messagebox.showerror("错误", "未找到视频文件！")
        return
    try:
        idx = g_current_index.get()
        if idx < 0 or (len(subtitles) > 0 and idx >= len(subtitles)):
            idx = 0
        g_current_index.set(idx)

        cmd = ["mpv", video_path, f"--input-ipc-server={MPV_SOCKET_PATH}"]

        if show_subtitle.get():
            if subtitle_path and os.path.exists(subtitle_path):
                show_subtitle_window()
                cmd.append("--no-sub")
            #    cmd.append(f"--sub-file={subtitle_path}")
            #    print(f"加载字幕：{subtitle_path}")
            # else:
            #    messagebox.showwarning("警告", "显示字幕已选中，但未找到有效字幕文件")
        else:
            cmd.append("--no-sub")
            print("不加载字幕")

        cmd.append("--geometry=0:0")  # 设置位置
        cmd.append("--autofit=1450x1000")  # 设置大小（固定）
        cmd.append(" --border=no ")

        subprocess.Popen(cmd)
        time.sleep(1)
        paused = False

        # 👇 如果勾选了“全屏”，则让 mpv 进入全屏
        if fullscreen.get():
            set_fullscreen(True)
        threading.Thread(target=auto_repeat_all, daemon=True).start()
    except Exception as e:
        messagebox.showerror("启动失败", f"无法启动 mpv：{e}")


# === 控制播放 ===
def toggle_pause():
    global paused
    paused = not paused
    if paused:
        pause_mpv()
    else:
        resume_mpv()
    toggle_button.config(text="继续播放" if paused else "暂停播放")


def seek_to(seconds):
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "time-pos", seconds]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
            print(f"seek_to success")
            time.sleep(0.1)
        return True
    except Exception as e:
        print(f"seek_to，通信错误:无法连接 mpv, {e}")
        # messagebox.showerror("通信错误", f"无法连接 mpv：{e}")
    return False


def pause_mpv():
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "pause", True]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
            print(f"pause_mpv success")
            time.sleep(0.1)
    except Exception as e:
        print(f"pause_mpv失败: {e}")


def resume_mpv():
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "pause", False]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
            print(f"resume_mpv success")
            time.sleep(0.1)
    except Exception as e:
        print(f"resume_mpv失败: {e}")


def save_all_params():
    save_params(
        "params.json",  # 从 params.json 加载参数
        video_path=video_path,
        f_current_index=g_current_index.get(),
        f_show_subtitle=show_subtitle.get(),
        f_fullscreen=fullscreen.get(),
        f_subtitle_offset=subtitle_offset.get(),
        f_subtitle_ch_first=subtitle_ch_first.get(),
        f_repeat_entry=repeat_entry.get(),
        f_repeat_intrval_entry=repeat_intrval_entry.get(),
        f_continue_entry=continue_entry.get(),
        f_pause_entry=pause_entry.get(),
        f_subtitles_entry=subtitles_entry.get(),
        f_speed_slider=speed_slider.get(),
    )


def auto_repeat_all():
    speed = 1.0
    playback_counts = 0
    index = 0
    try:
        while True:
            if index != g_current_index.get():
                index = g_current_index.get()
                playback_counts = 0
            if index + 1 >= len(subtitles):
                break

            if paused:
                time.sleep(0.1)
                continue

            try:
                repeat_count = int(repeat_entry.get())
            except:
                repeat_count = 3

            try:
                repeat_intrval_sec = int(repeat_intrval_entry.get())
            except:
                repeat_intrval_sec = 0

            try:
                delay_after_repeat = int(pause_entry.get())
                if delay_after_repeat < 0:
                    delay_after_repeat = 0
            except:
                delay_after_repeat = 0

            try:
                continue_count = int(continue_entry.get())
                if continue_count < 0:
                    continue_count = 0
            except:
                continue_count = 0

            update_progress_controls()
            Interrupted = False
            left_continue_count = continue_count
            for _ in range(repeat_count):
                try:
                    start_sec = subtitles[index][0] + adjust_begin_slider.get()
                    if playback_counts == 0 and index - 1 >= 0:
                        start_sec = subtitles[index - 1][1] + adjust_end_slider.get() + 0.1

                    end_sec = subtitles[index][1] + adjust_end_slider.get()
                except Exception as e:
                    print(f"auto_repeat_all Exception: {e}")

                if abs(speed_slider.get() - speed) > 1e-9 and speed_slider.get() > 0:
                    speed = speed_slider.get()
                    try:
                        with open(MPV_SOCKET_PATH, "wb") as sock:
                            command = {"command": ["set_property", "speed", speed]}
                            sock.write((json.dumps(command) + "\n").encode("utf-8"))
                    except Exception as e:
                        print(f"设置播放速度失败: {e}")

                duration = end_sec - start_sec
                if duration <= 0.1:
                    start_sec = max(start_sec - 0.15, 0)
                    end_sec = end_sec + 0.15
                    duration = end_sec - start_sec
                duration_speed = duration / speed
                duration_half = duration / 2

                if not seek_to(start_sec):
                    print("auto_repeat_all exit")
                    return
                playback_counts += 1
                current_repeat_label.after(
                    0,
                    lambda: current_repeat_label.config(text="当前复读次数: " + str(playback_counts)),
                )
                start_time = time.time()
                while time.time() - start_time < duration_speed:
                    if g_current_index.get() != index or paused:
                        Interrupted = True
                        break
                    time.sleep(0.01)
                    continue

                if Interrupted:
                    break

                if left_continue_count > 1:
                    left_continue_count -= 1
                    continue
                elif repeat_intrval_sec > 0:
                    left_continue_count = continue_count
                    pause_mpv()
                    if not seek_to(start_sec + duration_half):
                        print("auto_repeat_all exit")
                        return
                    elapsed = 0
                    while elapsed < repeat_intrval_sec * duration_speed:
                        time.sleep(0.1)
                        # 可以在这里插入中断判断等逻辑，比如检查是否暂停/取消
                        elapsed += 0.1
                        if g_current_index.get() != index or paused:
                            Interrupted = True
                            break
                    if not paused:
                        resume_mpv()
                    if Interrupted:
                        break

            if Interrupted:
                continue

            elapsed = 0
            if delay_after_repeat > 0:
                pause_mpv()
                while elapsed < delay_after_repeat * duration_speed:
                    time.sleep(0.1)
                    # 可以在这里插入中断判断等逻辑，比如检查是否暂停/取消
                    elapsed += 0.1
                    if g_current_index.get() != index or paused:
                        Interrupted = True
                        break
                if not paused:
                    resume_mpv()

            if Interrupted:
                continue
            g_current_index.increment()
            if subtitle_offset.get():
                # 重置字幕偏移
                adjust_begin_slider.set(0.0)
                adjust_end_slider.set(0.0)
    except Exception as e:
        print(f"auto_repeat_all exit: {e}")
    finally:
        print("无论是否异常，这里都会执行（类似析构）")
        save_all_params()
        messagebox.showwarning("警告", "循环控制线程已经退出")


# === 控件联动 ===
def on_slider_change(value):
    g_current_index.set(int(float(value)))
    current_index_label.config(text=str(g_current_index.get()))
    update_count_label()


def on_prev(bPage=False):
    num = 1
    if bPage:
        try:
            num = int(subtitles_entry.get())
        except ValueError:
            num = 1
    if g_current_index.get() - num > 0:
        g_current_index.set(g_current_index.get() - num)
        if subtitle_offset.get():
            # 重置字幕偏移
            adjust_begin_slider.set(0.0)
            adjust_end_slider.set(0.0)
        update_progress_controls()


def on_next(bPage=False):
    num = 1
    if bPage:
        try:
            num = int(subtitles_entry.get())
        except ValueError:
            num = 1
    if g_current_index.get() + num < len(subtitles) - 1:
        g_current_index.set(g_current_index.get() + num)
        if subtitle_offset.get():
            # 重置字幕偏移
            adjust_begin_slider.set(0.0)
            adjust_end_slider.set(0.0)
        update_progress_controls()


def update_main_subtitles(start, end, index):
    for i in range(start, end):
        lines = [line for j, line in enumerate(subtitles[i][2].splitlines()) if j % 2 == 0]
        text = "\n".join(lines) + "\n"

        if i == index:
            subtitle_text.insert(tk.END, text, "center")
        else:
            subtitle_text.insert(tk.END, text, "faded")

    subtitle_text.insert(tk.END, "\n", "faded")

    for i in range(start, end):
        lines = [line for j, line in enumerate(subtitles[i][2].splitlines()) if j % 2 == 1]
        text = "\n".join(lines) + "\n"

        if i == index:
            subtitle_text.insert(tk.END, text, "center")
        else:
            subtitle_text.insert(tk.END, text, "faded")


def update_chinese_subtitles(start, end, index):
    if subtitles_sub2 is None:
        return  # 如果没有中文字幕，直接返回

    for i in range(start, end):
        lines = [line for j, line in enumerate(subtitles_sub2[i][2].splitlines())]
        text = "\n".join(lines) + "\n"

        if i == index:
            subtitle_text.insert(tk.END, text, "center")
        else:
            subtitle_text.insert(tk.END, text, "faded")

    subtitle_text.insert(tk.END, "\n", "faded")


def update_extra_subtitles(start, end, index, N=10):
    if subtitles_sub2 is not None:
        subtitle_text.insert(tk.END, "\n\n\n\n\n\n\n\n\n\n", "faded")
        subtitle_text.insert(tk.END, "sub2 subtitles:\n", "faded")
        start_pre = max(0, start - N)
        end_next = min(end + N, len(subtitles))
        for i in range(start_pre, end_next):
            lines = [line for j, line in enumerate(subtitles_sub2[i][2].splitlines())]
            text = "\n".join(lines) + "\n"
            if i == start:
                subtitle_text.insert(tk.END, "\n///\n", "faded")
            elif i == end:
                subtitle_text.insert(tk.END, "///\n\n", "faded")

            if i == index:
                subtitle_text.insert(tk.END, text, "center")
            else:
                subtitle_text.insert(tk.END, text, "faded")

        subtitle_text.insert(tk.END, "\n///\n", "faded")
        for i in range(start_pre, end_next):
            lines = [line for j, line in enumerate(subtitles[i][2].splitlines()) if j % 2 == 0]
            text = "\n".join(lines) + "\n"
            if i == start:
                subtitle_text.insert(tk.END, "\n///\n", "faded")
            elif i == end:
                subtitle_text.insert(tk.END, "///\n\n", "faded")

            if i == index:
                subtitle_text.insert(tk.END, text, "center")
            else:
                subtitle_text.insert(tk.END, text, "faded")

        subtitle_text.insert(tk.END, "\n\n\n\n\n\n\n\n\n\n", "faded")


# 更新进度控件
def update_subtitles_control():
    global subtitle_display_window
    if len(subtitles) == 0 or subtitle_display_window is None:
        return

    index = g_current_index.get()
    N = 10  # 每页显示 N 行字幕
    try:
        N = int(subtitles_entry.get())
        subtitle_text.delete("1.0", tk.END)
    except Exception as e:
        print(f"subtitles_entry失败: {e}")
    # 计算起始行：找到当前 index 所在的 N 行区块的起始下标
    start = (index // N) * N
    end = min(start + N, len(subtitles))
    subtitle_text.delete("1.0", tk.END)
    subtitle_text.insert(tk.END, f"{index}/{len(subtitles)}\n", "faded")

    if subtitle_ch_first.get():
        update_chinese_subtitles(start, end, index)
        subtitle_text.insert(tk.END, "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n", "faded")
        update_main_subtitles(start, end, index)
    else:
        update_main_subtitles(start, end, index)
        subtitle_text.insert(tk.END, "\n\n\n\n\n\n\n\n\n\n", "faded")
        update_chinese_subtitles(start, end, index)

    update_extra_subtitles(start, end, index, N)


# 更新进度控件
def update_progress_controls():
    if len(subtitles) == 0:
        return
    index = g_current_index.get()
    skip_slider.config(to=len(subtitles) - 1)
    skip_slider.set(index)
    current_index_label.config(text=str(index))
    update_count_label()
    update_subtitles_control()


def update_count_label():
    count_label.config(text=f"/ {len(subtitles)}")


def toggle_pause2():
    toggle_pause()
    toggle_pause()


def minimize_other(event=None):
    global paused, subtitle_display_window
    if event.widget != subtitle_display_window:
        return  # 确保是根窗口触发的事件

    windows = gw.getWindowsWithTitle("mpv")
    if windows:
        mpv_window = windows[0]
        mpv_window.minimize()
    print("窗口最小化")


def restore_other(event=None):
    global paused, subtitle_display_window
    if event.widget != subtitle_display_window:
        return  # 确保是根窗口触发的事件

    windows = gw.getWindowsWithTitle("mpv")
    if windows:
        mpv_window = windows[0]
        mpv_window.restore()
    print("窗口还原")


def on_close():
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["quit"]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"on_close False: {e}")

    save_all_params()
    root.destroy()
    print("on_close called, parameters saved and root window closed.")


def on_focus_in(event):
    global subtitle_display_window
    if event.widget != subtitle_display_window:
        return  # 确保是根窗口触发的事件
    print("window got focus!")
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "ontop", True]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"on_focus_in True: {e}")

    time.sleep(0.1)  # 确保 mpv 窗口已准备好接收命令
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "ontop", False]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"on_focus_in False: {e}")


# === UI ===
root = tk.Tk()
root.title("Subtitle Repeater (Atomic with Delay & Subtitle Toggle)")
root.geometry("470x600+1450+340")
root.protocol("WM_DELETE_WINDOW", on_close)

tk.Button(root, text="选择视频文件", command=select_video).pack(pady=5)
video_label = tk.Label(root, text="视频: 未选择")
video_label.pack()

tk.Button(root, text="选择字幕文件 (.srt)", command=select_subtitle).pack(pady=5)
subtitle_label = tk.Label(root, text="字幕: 未选择")
subtitle_label.pack()

options_frame = tk.Frame(root)
options_frame.pack()


show_subtitle = tk.BooleanVar(value=f_show_subtitle)
tk.Checkbutton(options_frame, text="显示字幕", variable=show_subtitle).pack(side=tk.LEFT, padx=10)

fullscreen = tk.BooleanVar(value=f_fullscreen)
tk.Checkbutton(options_frame, text="全屏", variable=fullscreen).pack(side=tk.LEFT)

subtitle_offset = tk.BooleanVar(value=f_subtitle_offset)
tk.Checkbutton(options_frame, text="重置字幕偏移", variable=subtitle_offset).pack(side=tk.LEFT, padx=10)

subtitle_ch_first = tk.BooleanVar(value=f_subtitle_ch_first)
tk.Checkbutton(options_frame, text="中文字幕在前", variable=subtitle_ch_first).pack(side=tk.LEFT, padx=10)

repeat_frame = tk.Frame(root)
repeat_frame.pack(pady=3)
tk.Label(repeat_frame, text="复读次数:").pack(side=tk.LEFT)
repeat_entry = tk.Entry(repeat_frame, width=5)
repeat_entry.insert(0, f_repeat_entry)
repeat_entry.pack(side=tk.LEFT)

tk.Label(repeat_frame, text="复读间隔:").pack(side=tk.LEFT)
repeat_intrval_entry = tk.Entry(repeat_frame, width=5)
repeat_intrval_entry.insert(0, f_repeat_intrval_entry)
repeat_intrval_entry.pack(side=tk.LEFT)

current_repeat_label = tk.Label(repeat_frame, text="当前复读次数: 0", width=20)
current_repeat_label.pack(side=tk.LEFT)

pause_frame = tk.Frame(root)
pause_frame.pack(pady=3)
tk.Label(pause_frame, text="连续复读次数:").pack(side=tk.LEFT)
continue_entry = tk.Entry(pause_frame, width=5)
continue_entry.insert(0, f_continue_entry)
continue_entry.pack(side=tk.LEFT)

tk.Label(pause_frame, text="复读后暂停:").pack(side=tk.LEFT)
pause_entry = tk.Entry(pause_frame, width=5)
pause_entry.insert(0, f_pause_entry)
pause_entry.pack(side=tk.LEFT)


tk.Label(pause_frame, text="显示字幕行数:").pack(side=tk.LEFT)
subtitles_entry = tk.Entry(pause_frame, width=5)
subtitles_entry.insert(0, f_subtitles_entry)
subtitles_entry.pack(side=tk.LEFT)

# 调整播放开始时间
adjust_begin = tk.Frame(root)
adjust_begin.pack(pady=3)
tk.Label(adjust_begin, text="调整播放开始时间:").pack(side=tk.LEFT)
adjust_begin_slider = tk.Scale(adjust_begin, from_=-2.0, to=+2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200)
adjust_begin_slider.pack(side=tk.LEFT)
adjust_begin_slider.set(0.0)  # 默认 0 秒

# 调整播放结束时间
adjust_end = tk.Frame(root)
adjust_end.pack(pady=3)
tk.Label(adjust_end, text="调整播放结束时间:").pack(side=tk.LEFT)
adjust_end_slider = tk.Scale(adjust_end, from_=-2.0, to=+2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200)
adjust_end_slider.pack(side=tk.LEFT)
adjust_end_slider.set(0.0)  # 默认 0 秒

# 播放速度设置
speed_frame = tk.Frame(root)
speed_frame.pack(pady=3)
tk.Label(speed_frame, text="播放速度:").pack(side=tk.LEFT)

speed_slider = tk.Scale(speed_frame, from_=0.1, to=2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200)
speed_slider.set(f_speed_slider)  # 默认 1 倍速
speed_slider.pack(side=tk.LEFT)

skip_slider = tk.Scale(root, from_=0, to=10, orient=tk.HORIZONTAL, length=300, command=on_slider_change)
skip_slider.pack()

skip_frame = tk.Frame(root)
skip_frame.pack(pady=3)
current_index_label = tk.Label(skip_frame, text="0", width=5)
current_index_label.pack(side=tk.LEFT)
count_label = tk.Label(skip_frame, text="/ 0")
count_label.pack(side=tk.LEFT, padx=5)
tk.Button(skip_frame, text="上一句", command=on_prev).pack(side=tk.LEFT, padx=5)
tk.Button(skip_frame, text="下一句", command=on_next).pack(side=tk.LEFT)

tk.Button(root, text="启动 mpv 播放器并开始复读", command=start_mpv).pack(pady=10)
toggle_button = tk.Button(root, text="暂停播放", command=toggle_pause)
toggle_button.pack(pady=5)

if os.path.exists(video_path):
    update_video()  # 如果视频路径已存在，更新视频信息


def toggle_window_state():
    global subtitle_display_window
    if keyboard.is_pressed("ctrl") and keyboard.is_pressed("d"):
        print("真正触发了 ctrl+d")
        if subtitle_display_window:
            if subtitle_display_window.state() == "normal":
                subtitle_display_window.iconify()  # 最小化
            elif subtitle_display_window.state() == "iconic":
                subtitle_display_window.deiconify()  # 还原
    else:
        print("没有触发 ctrl+d")


def display_on_top():
    if keyboard.is_pressed("ctrl") and keyboard.is_pressed("t"):
        print("真正触发了 ctrl+t")

        if root.state() == "iconic":
            root.deiconify()  # 确保窗口可见
        else:
            root.iconify()  # 隐藏窗口
    else:
        print("没有触发 ctrl+t")


keyboard.add_hotkey("ctrl+d", lambda: toggle_window_state())
keyboard.add_hotkey("ctrl+t", lambda: display_on_top())

root.mainloop()
