import os
import sys


def convert_files(directory, enc="gbk", extension=".txt"):
    # 遍历指定目录下的所有文件
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extension):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, encoding=enc) as f:
                        content = f.read()

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"成功转换: {file_path}")

                except UnicodeDecodeError:
                    print(f"跳过 (非GBK编码或读取失败): {file_path}")
                except OSError as e:
                    print(f"处理出错 {file_path}: {e}")


if __name__ == "__main__":
    # 默认转换当前脚本所在的目录
    target_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    if not os.path.isdir(target_dir):
        print(f"错误: 目录不存在 - {target_dir}")
        sys.exit(1)

    print(f"开始转换目录: {target_dir} 下的 .txt 文件...")
    convert_files(target_dir, enc="gbk", extension=".txt")
    print("转换完成！")
