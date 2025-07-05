import os
import sys
import pysubs2

# 切换工作目录到脚本所在目录
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)


def apply_style(subs):
    style = subs.styles.get("Default", pysubs2.SSAStyle())
    style.fontsize = 24
    style.primarycolor = pysubs2.Color(255, 0, 0, 0)  # 红色
    style.bold = True
    style.alignment = 5  # 居中
    style.marginv = 0
    subs.styles["Default"] = style


def convert_to_ass(input_path, output_path):
    try:
        subs = pysubs2.load(input_path)
        apply_style(subs)
        subs.save(output_path)
        print(f"✅ 转换成功：{input_path} → {output_path}")
    except Exception as e:
        print(f"❌ 转换失败：{input_path} 错误: {e}")


def batch_convert(folder="."):
    # 构建文件基名索引，记录有哪些文件类型存在
    base_map = {}
    for filename in os.listdir(folder):
        name, ext = os.path.splitext(filename)
        ext = ext.lower()
        if ext in [".srt", ".vtt"]:
            base_map.setdefault(name, {})[ext] = filename

    for name, types in base_map.items():
        if ".srt" in types:
            input_file = types[".srt"]
        elif ".vtt" in types:
            input_file = types[".vtt"]
        else:
            continue

        input_path = os.path.join(folder, input_file)
        output_path = os.path.join(folder, name + ".ass")
        convert_to_ass(input_path, output_path)


if __name__ == "__main__":
    batch_convert()
