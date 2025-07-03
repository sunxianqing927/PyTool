import os
import shutil
import pysrt
from datetime import datetime

# === 可调参数 ===
FILENAME = "Silicon.Valley.S01E01.en.srt"  # 字幕文件名
OFFSET_SECONDS = -0.2                       # 偏移秒数（正数为延后，负数为提前）
REMOVE_DUPLICATES = False                  # 是否去除时间重复的字幕

# === 转换 float 秒为 SubRipTime ===
def float_to_srttime(seconds):
    if seconds < 0:
        seconds = 0
    total_ms = int(seconds * 1000)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return pysrt.SubRipTime(hours=hours, minutes=minutes, seconds=secs, milliseconds=ms)

# === 主函数 ===
def shift_srt_times(filename, offset_seconds):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(script_dir, filename)

    if not os.path.exists(filepath):
        print(f"❌ 文件不存在: {filepath}")
        return

    # 备份原始文件
    backup_dir = os.path.join(script_dir, "backup_srt")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{filename}.{timestamp}.bak.srt")
    shutil.copy2(filepath, backup_path)
    print(f"✅ 已备份原文件到: {backup_path}")

    # 读取字幕
    try:
        subs = pysrt.open(filepath, encoding='utf-8')
    except Exception as e:
        print(f"❌ 无法读取字幕文件: {e}")
        return

    new_subs = []
    for sub in subs:
        start_sec = sub.start.ordinal / 1000 + offset_seconds
        end_sec = sub.end.ordinal / 1000 + offset_seconds
        if end_sec <= 0:
            continue  # 丢弃无效段
        sub.start = float_to_srttime(start_sec)
        sub.end = float_to_srttime(end_sec)
        new_subs.append(sub)

    # 去重（可选）
    if REMOVE_DUPLICATES:
        seen = set()
        filtered = []
        for sub in new_subs:
            key = (sub.start.ordinal, sub.end.ordinal)
            if key not in seen:
                seen.add(key)
                filtered.append(sub)
        new_subs = filtered
        print(f"🧹 去重后剩余字幕条数: {len(new_subs)}")

    # 保存文件
    try:
        pysrt.SubRipFile(items=new_subs).save(filepath, encoding='utf-8')
        print(f"✅ 修改完成，字幕文件已保存: {filepath}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")

# === 执行 ===
if __name__ == "__main__":
    shift_srt_times(FILENAME, OFFSET_SECONDS)
