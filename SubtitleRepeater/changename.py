import os
import re

# 配置
folder = "."  # 当前目录
show_name = "Silicon.Valley"
season_num = 4  # 第一季
ext_list = [".mp4", ".mkv", ".avi"]  # 支持的视频后缀

# 正则匹配示例：
# 假设原文件名中含有 “硅谷第一季01” 这种格式，01代表集数
pattern = re.compile(r"硅谷第四季0*(\d+)", re.IGNORECASE)

files = os.listdir(folder)

for filename in files:
    name, ext = os.path.splitext(filename)
    if ext.lower() not in ext_list:
        continue
    m = pattern.search(name)
    if m:
        episode_num = int(m.group(1))
        new_name = f"{show_name}.S{season_num:02d}E{episode_num:02d}{ext}"
        print(f"重命名: {filename}  ->  {new_name}")
        os.rename(os.path.join(folder, filename), os.path.join(folder, new_name))
