import tkinter as tk
import time
import threading
import winsound

# 倒计时间段（格式为 "HH:MM:SS"）
countdown_stages = ["00:30:00", "00:01:30"]  # 10秒，30秒为例
alarm_duration = 5  # 响铃持续时间（秒）


def time_str_to_seconds(timestr):
    """将时间字符串 HH:MM:SS 转为秒数"""
    h, m, s = map(int, timestr.split(":"))
    return h * 3600 + m * 60 + s


def format_seconds(seconds):
    """将秒数格式化为 HH:MM:SS 字符串"""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class CountdownApp:
    def __init__(self, root):
        self.root = root
        self.root.title("循环倒计时工具")
        self.root.geometry("300x150")

        self.stage_index = 0
        self.running = True

        self.label_stage = tk.Label(root, text="准备开始", font=("Helvetica", 14))
        self.label_stage.pack(pady=10)

        self.label_time = tk.Label(root, text="", font=("Helvetica", 32))
        self.label_time.pack()

        self.start_loop()

    def start_loop(self):
        thread = threading.Thread(target=self.run_loop, daemon=True)
        thread.start()

    def run_loop(self):
        while self.running:
            # 当前阶段倒计时时长（字符串 -> 秒）
            duration_str = countdown_stages[self.stage_index]
            duration_sec = time_str_to_seconds(duration_str)

            self.update_stage_label(f"倒计时 {duration_str}")
            self.countdown(duration_sec)

            self.update_stage_label(f"响铃 {alarm_duration} 秒")
            self.play_alarm()

            # 下一个阶段
            self.stage_index = (self.stage_index + 1) % len(countdown_stages)

    def countdown(self, total_seconds):
        for remaining in range(total_seconds, 0, -1):
            self.update_time_label(format_seconds(remaining))
            time.sleep(1)
        self.update_time_label("00:00:00")

    def play_alarm(self):
        for _ in range(alarm_duration):
            winsound.Beep(1000, 500)  # 响500ms
            time.sleep(1)

    def update_time_label(self, text):
        self.label_time.config(text=text)

    def update_stage_label(self, text):
        self.label_stage.config(text=text)

    def stop(self):
        self.running = False


# 运行程序
if __name__ == "__main__":
    root = tk.Tk()
    app = CountdownApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.stop(), root.destroy()))
    root.mainloop()
