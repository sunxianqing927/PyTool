import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import json
import time
import pysrt
import pysubs2
import re
import datetime
import threading
import keyboard  # 全局键盘监听
from tkinter import font
import pygetwindow as gw


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
g_current_index = AtomicInteger(0)
paused = False
close_mpv = False  # 用于控制 mpv 播放器的关闭

f_current_index = 0
f_show_subtitle = True
f_fullscreen = False
f_second_screen = False
f_subtitle_offset = False
f_repeat_entry = "5"
f_repeat_intrval_entry = "5"
f_continue_entry = "5"
f_pause_entry = "5"
f_speed_slider = 1.0

load_params("params.json")

g_current_index.set(f_current_index)  # 设置初始索引


# === 自动查找字幕 ===
def auto_find_subtitle():
    global subtitle_path
    if not video_path:
        return
    base = os.path.splitext(video_path)[0]
    for ext in [".ass", ".srt"]:
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
    global subtitles
    if not os.path.exists(subtitle_path):
        messagebox.showerror("错误", "字幕文件未找到！")
        return []

    try:
        if subtitle_path.lower().endswith(".ass"):
            subs = pysubs2.load(subtitle_path)
            subtitles = [
                (
                    line.start / 1000,
                    line.end / 1000,
                    line.text.strip().replace("\\N", " ").replace("\n", " "),
                )
                for line in subs
                if line.type == "Dialogue"
            ]

        elif subtitle_path.lower().endswith(".srt"):
            subs = pysrt.open(subtitle_path)
            subtitles = [
                (
                    sub.start.ordinal / 1000,
                    sub.end.ordinal / 1000,
                    sub.text.strip(),
                )
                for sub in subs
            ]

        #    elif subtitle_path.lower().endswith(".vtt"):
        #    subs = webvtt.read(subtitle_path)
        #    subtitles = []
        #    for caption in subs:
        #    h1, m1, s1 = caption.start.split(":")
        #    s1, ms1 = s1.split(".")
        #    start_sec = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
        #    h2, m2, s2 = caption.end.split(":")
        #    s2, ms2 = s2.split(".")
        #    end_sec = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000
        #    subtitles.append(
        #    (start_sec, end_sec, caption.text.strip().replace("\n", " "))
        #    )

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
    path = filedialog.askopenfilename(
        filetypes=[("视频文件", "*.mp4;*.mkv;*.avi"), ("所有文件", "*.*")]
    )
    if path:
        video_path = path
        g_current_index.set(0)
        update_video()


def select_subtitle():
    global subtitle_path
    path = filedialog.askopenfilename(
        filetypes=[("字幕文件", "*.ass;*.srt"), ("所有文件", "*.*")]
    )
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


subtitle_display_window = None
subtitle_labels = []


# 将秒转为 SRT 时间格式
def seconds_to_srt_timestamp(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


# 获取以视频文件名命名的 notes.srt 文件名
def get_notes_filename() -> str:
    if not video_path:
        return "notes.srt"
    base = os.path.splitext(video_path)[0]  # 不用 basename，保留路径
    return f"{base}_notes.srt"


# 获取 SRT 文件中下一个字幕编号
def get_next_srt_number(filename: str) -> int:
    """根据最后一个时间戳行，获取它的上一行作为编号，返回下一个字幕编号"""
    if not os.path.exists(filename):
        return 1

    with open(filename, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    timestamp_pattern = re.compile(
        r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}"
    )

    for i in range(len(lines) - 1, 0, -1):
        if timestamp_pattern.match(lines[i]):
            try:
                return int(lines[i - 1]) + 1
            except:
                break
    return 1


# 保存当前字幕为新的 SRT 条目
def save_subtitle_to_srt(index: int):
    if index < 0 or index >= len(subtitles):
        return

    start, end, text = subtitles[index]
    srt_filename = get_notes_filename()
    next_number = get_next_srt_number(srt_filename)

    srt_block = f"""{next_number}
{seconds_to_srt_timestamp(start)} --> {seconds_to_srt_timestamp(end)}
{text.strip()}

"""
    with open(srt_filename, "a", encoding="utf-8") as f:
        f.write(srt_block)

    messagebox.showinfo("保存成功", f"字幕已追加到：{srt_filename}")


# 回调函数工厂：用于绑定点击字幕标签
def on_label_click_factory(idx_offset: int):
    def callback(event):
        real_index = g_current_index.get() + idx_offset
        save_subtitle_to_srt(real_index)

    return callback


def show_subtitle_window():
    global subtitle_display_window, subtitle_labels
    if subtitle_display_window and subtitle_display_window.winfo_exists():
        return  # 避免重复创建

    subtitle_display_window = tk.Toplevel(root)
    subtitle_display_window.title("字幕显示")
    subtitle_display_window.configure(bg="black")
    # subtitle_display_window.state("zoomed")  # 最大化窗口
    subtitle_display_window.geometry("1920x300+0+0")
    # subtitle_display_window.attributes("-topmost", True)  # 置顶显示

    subtitle_labels = []
    for i in range(3):
        lbl = tk.Label(
            subtitle_display_window,
            text="",
            fg="white",
            bg="black",
            font=("Helvetica", 20),
            wraplength=1600,
            justify="center",
            anchor="center",
        )
        lbl.pack(expand=True, fill=tk.BOTH)
        lbl.bind(
            "<Double-Button-1>", on_label_click_factory(i - 1)
        )  # -1: 上一句, 0: 当前, +1: 下一句
        subtitle_labels.append(lbl)

    update_subtitle_window()  # 初始显示


def update_subtitle_window():
    if not subtitle_labels or not subtitles:
        return
    index = g_current_index.get()
    prev_text = subtitles[index - 1][2] if index > 0 else ""
    curr_text = subtitles[index][2]

    lines = curr_text.splitlines()
    odd_lines = [line for i, line in enumerate(lines) if i % 2 == 0]
    even_lines = [f"[ {line} ]" for i, line in enumerate(lines) if i % 2 == 1]
    odd_text = "\n".join(odd_lines)
    even_text = "\n".join(even_lines)
    curr_text = f"{odd_text}\n{even_text}"

    next_text = subtitles[index + 1][2] if index + 1 < len(subtitles) else ""

    subtitle_labels[0].config(text=prev_text, font=("Helvetica", 18), fg="#888888")
    subtitle_labels[1].config(
        text=curr_text, font=("Helvetica", 32, "bold"), fg="#C0A000"  # 金黄色
    )
    subtitle_labels[2].config(text=next_text, font=("Helvetica", 18), fg="#888888")


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

        # 设置播放屏幕位置
        if second_screen.get():
            cmd.append("--geometry=0:-1080")  # 第二屏（上方）
            cmd.append(" --autofit-larger=100%x100% ")
        else:
            cmd.append("--geometry=433:360")  # 设置位置
            cmd.append("--autofit=1196x670")  # 设置大小（固定）

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
        f_second_screen=second_screen.get(),
        f_subtitle_offset=subtitle_offset.get(),
        f_repeat_entry=repeat_entry.get(),
        f_repeat_intrval_entry=repeat_intrval_entry.get(),
        f_continue_entry=continue_entry.get(),
        f_pause_entry=pause_entry.get(),
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
                delay_after_repeat = float(pause_entry.get())
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

            update_subtitle_window()
            update_progress_controls()
            Interrupted = False
            left_continue_count = continue_count
            for _ in range(repeat_count):
                try:
                    start_sec = subtitles[index][0] + adjust_begin_slider.get()
                    if playback_counts == 0 and index - 1 >= 0:
                        start_sec = (
                            subtitles[index - 1][1] + adjust_end_slider.get() + 0.1
                        )

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
                duration_speed = duration / speed
                duration_half = duration / 2

                if not seek_to(start_sec):
                    print("auto_repeat_all exit")
                    return
                playback_counts += 1
                current_repeat_label.after(
                    0,
                    lambda: current_repeat_label.config(
                        text="当前复读次数: " + str(playback_counts)
                    ),
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


def on_prev():
    if g_current_index.get() > 0:
        g_current_index.decrement()
        if subtitle_offset.get():
            # 重置字幕偏移
            adjust_begin_slider.set(0.0)
            adjust_end_slider.set(0.0)
        update_progress_controls()


def on_next():
    if g_current_index.get() < len(subtitles) - 1:
        g_current_index.increment()
        if subtitle_offset.get():
            # 重置字幕偏移
            adjust_begin_slider.set(0.0)
            adjust_end_slider.set(0.0)
        update_progress_controls()


# 更新进度控件
def update_progress_controls():
    if len(subtitles) == 0:
        return
    index = g_current_index.get()
    skip_slider.config(to=len(subtitles) - 1)
    skip_slider.set(index)
    current_index_label.config(text=str(index))

    subtitle_text.delete("1.0", tk.END)
    # Handle previous, current, and next subtitles
    new_text = ""
    for i in [index - 1, index, index + 1]:
        if 0 <= i < len(subtitles):
            new_text = (
                "\n".join(
                    [
                        line
                        for i, line in enumerate(subtitles[i][2].splitlines())
                        if i % 2 == 0
                    ]
                )
                + "\n"
            )
            if i == index:
                subtitle_text.insert(tk.END, new_text, "center")
            else:
                subtitle_text.insert(tk.END, new_text, "faded")

    update_count_label()


def update_count_label():
    count_label.config(text=f"/ {len(subtitles)}")


def toggle_pause2():
    toggle_pause()
    toggle_pause()


def minimize_other(event=None):
    if event.widget != root:
        print("窗口最小化事件不是由根窗口触发的")
        return  # 确保是根窗口触发的事件
    global subtitle_display_window, paused
    if subtitle_display_window and subtitle_display_window.winfo_exists():
        subtitle_display_window.wm_state("iconic")  # 最小化另一个窗口

    paused = False  # 设置暂停状态
    toggle_pause()  # 切换暂停状态

    windows = gw.getWindowsWithTitle("mpv")
    if windows:
        mpv_window = windows[0]
        mpv_window.minimize()
    print("窗口最小化")


def restore_other(event=None):
    if event.widget != root:
        print("窗口还原事件不是由根窗口触发的")
        return  # 确保是根窗口触发的事件
    global subtitle_display_window
    if subtitle_display_window and subtitle_display_window.winfo_exists():
        subtitle_display_window.wm_state("normal")

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
        print(f"on_focus_in False: {e}")

    save_all_params()
    root.destroy()
    print("on_close called, parameters saved and root window closed.")


def on_focus_in(event):
    print("Root window got focus!")
    if subtitle_display_window:
        subtitle_display_window.attributes("-topmost", True)
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "ontop", True]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"on_focus_in True: {e}")

    time.sleep(0.1)  # 确保 mpv 窗口已准备好接收命令
    if subtitle_display_window:
        subtitle_display_window.attributes("-topmost", False)
    try:
        with open(MPV_SOCKET_PATH, "wb") as sock:
            command = {"command": ["set_property", "ontop", False]}
            sock.write((json.dumps(command) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"on_focus_in False: {e}")


# === UI ===
root = tk.Tk()
root.title("Subtitle Repeater (Atomic with Delay & Subtitle Toggle)")
root.geometry("420x600+0+340")
root.bind("<Unmap>", minimize_other)  # 最小化时触发
root.bind("<Map>", restore_other)
root.bind("<FocusIn>", on_focus_in)

root.protocol("WM_DELETE_WINDOW", on_close)


tk.Button(root, text="选择视频文件", command=select_video).pack(pady=5)
video_label = tk.Label(root, text="视频: 未选择")
video_label.pack()

tk.Button(root, text="选择字幕文件 (.ass ,.srt)", command=select_subtitle).pack(pady=5)
subtitle_label = tk.Label(root, text="字幕: 未选择")
subtitle_label.pack()

options_frame = tk.Frame(root)
options_frame.pack()


show_subtitle = tk.BooleanVar(value=f_show_subtitle)
tk.Checkbutton(options_frame, text="显示字幕", variable=show_subtitle).pack(
    side=tk.LEFT, padx=10
)

fullscreen = tk.BooleanVar(value=f_fullscreen)
tk.Checkbutton(options_frame, text="全屏", variable=fullscreen).pack(side=tk.LEFT)

second_screen = tk.BooleanVar(value=f_second_screen)  # 默认在第二屏幕
tk.Checkbutton(options_frame, text="在第二屏幕播放", variable=second_screen).pack(
    side=tk.LEFT, padx=10
)

subtitle_offset = tk.BooleanVar(value=f_subtitle_offset)  # 默认在第二屏幕
tk.Checkbutton(options_frame, text="重置字幕偏移", variable=subtitle_offset).pack(
    side=tk.LEFT, padx=10
)


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

tk.Label(pause_frame, text="复读后暂停N:").pack(side=tk.LEFT)
pause_entry = tk.Entry(pause_frame, width=5)
pause_entry.insert(0, f_pause_entry)
pause_entry.pack(side=tk.LEFT)

# 多行文本框用于显示字幕
subtitle_text = tk.Text(root, width=50, height=5, wrap="word", bg=root["bg"])
subtitle_text.pack()

# 字体设置
base_font = font.Font(subtitle_text, subtitle_text.cget("font"))
bold_font = font.Font(subtitle_text, subtitle_text.cget("font"))
bold_font.configure(weight="bold")

# 中间行（主字幕）样式
subtitle_text.tag_configure("center", font=bold_font)

# 上下行（弱化字幕）样式
subtitle_text.tag_configure("faded", font=base_font, foreground="#888888")


# 调整播放开始时间
adjust_begin = tk.Frame(root)
adjust_begin.pack(pady=3)
tk.Label(adjust_begin, text="调整播放开始时间:").pack(side=tk.LEFT)
adjust_begin_slider = tk.Scale(
    adjust_begin, from_=-2.0, to=+2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200
)
adjust_begin_slider.pack(side=tk.LEFT)
adjust_begin_slider.set(0.0)  # 默认 0 秒

# 调整播放结束时间
adjust_end = tk.Frame(root)
adjust_end.pack(pady=3)
tk.Label(adjust_end, text="调整播放结束时间:").pack(side=tk.LEFT)
adjust_end_slider = tk.Scale(
    adjust_end, from_=-2.0, to=+2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200
)
adjust_end_slider.pack(side=tk.LEFT)
adjust_end_slider.set(0.0)  # 默认 0 秒

# 播放速度设置
speed_frame = tk.Frame(root)
speed_frame.pack(pady=3)
tk.Label(speed_frame, text="播放速度:").pack(side=tk.LEFT)

speed_slider = tk.Scale(
    speed_frame, from_=0.1, to=2.0, resolution=0.01, orient=tk.HORIZONTAL, length=200
)
speed_slider.set(f_speed_slider)  # 默认 1 倍速
speed_slider.pack(side=tk.LEFT)

skip_slider = tk.Scale(
    root, from_=0, to=10, orient=tk.HORIZONTAL, length=300, command=on_slider_change
)
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


def listen_global_key():
    # 线程安全地更新 label
    keyboard.add_hotkey("left", lambda: on_prev())
    keyboard.add_hotkey("right", lambda: on_next())
    keyboard.add_hotkey("p", lambda: toggle_pause())
    keyboard.add_hotkey("space", lambda: toggle_pause2())
    keyboard.wait()  # 保持监听线程运行


# 启动键盘监听线程
# threading.Thread(target=listen_global_key, daemon=True).start()


def listen_Focused_key(root):
    root.bind("<Left>", lambda event: on_prev())
    root.bind("<Right>", lambda event: on_next())
    root.bind("<p>", lambda event: toggle_pause())
    root.bind("<space>", lambda event: toggle_pause2())


listen_Focused_key(root)
root.mainloop()
