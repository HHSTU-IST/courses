import os
from glob import glob


def file_collect(folder, ext="docx"):
    files = glob(f"{folder}/*/*.{ext}")
    for f in files:
        dir = os.path.dirname(f).split("/")
        dir_p = dir[0] + "/" + dir[1] + "/"
        basename = os.path.basename(f)
        f_n = dir_p + basename
        print(f_n)
        os.rename(f, f_n)


if __name__ == "__main__":
    folder = "python"
    file_collect(folder)
