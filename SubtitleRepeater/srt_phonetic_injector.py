import os
import sys
import re
import json
import shutil

# 切换工作目录到脚本所在目录
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)


# 加载音标字典
with open("dictionary.json", "r", encoding="utf-8") as f:
    dictionary = json.load(f)


def get_pron_line(line):
    def replace_word(match):
        word = match.group()
        key = word.lower()
        if key in dictionary and "us_pron" in dictionary[key]:
            return dictionary[key]["us_pron"]
        else:
            return word  # 保留原单词

    # 替换所有英文单词，保留标点和结构
    return re.sub(r"\b[a-zA-Z]+(?:['-][a-zA-Z]+)*\b", replace_word, line)


# 遍历所有 .srt 文件
for filename in os.listdir("."):
    if filename.endswith(".srt"):
        # 备份原始文件
        backup_name = filename + ".bak"
        shutil.copyfile(filename, backup_name)
        print(f"🗂 已备份：{filename} → {backup_name}")

        output_lines = []
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            output_lines.append(lines[i])  # index line or timestamp
            if i + 1 < len(lines) and "-->" in lines[i]:
                j = i + 1
                while (
                    j < len(lines)
                    and lines[j].strip()
                    and not re.match(r"^\d+$", lines[j])
                ):
                    text_line = lines[j]
                    output_lines.append(text_line)
                    pron_line = get_pron_line(text_line)
                    if pron_line.strip():
                        output_lines.append(pron_line)
                    j += 1
                i = j
            else:
                i += 1

        # 覆盖原文件
        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(output_lines)

        print(f"✅ 处理完成并覆盖：{filename}")

print("🎉 所有字幕文件处理完成。")
