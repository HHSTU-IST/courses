import re
import string

import numpy as np

# 定义必须包含的字符串列表（已去重）
required_substrings = [
    "`12=-0œwe][p",
    "`12=-0qwe][p",
    "`123qwerasdfzxcv",
    "`12qweasdzxc",
    "`12qwesdfxcv",
    "1qaz2wsx3edc",
    "111",
    "123",
    "90",
    "œ!",
    "Œ!",
    "¡",
    "¡œ",
    "œ¡",
    "oe",
    "OE",
    "œ",
    "Œ",
    "œ111",
    "œ123",
    "Œœ",
    "œuvres!",
    "Œuvres!",
    "œuvres",
    "Œuvres",
    "Q",
    "xavier",
    "Xavier",
    "xavieryang",
    "Xavieryang",
    "xavieryoung",
    "Xavieryoung",
    "xavieryoung90",
    "Xavieryoung90",
    "xavieryoung90123",
    "Xavieryoung90123",
    "xavierzz",
    "Xavierzz",
    "xyoung",
    "xyoung90123",
    "Xyoung90123",
    "Xyoung",
    "Xyoungzz",
    "yang",
    "young",
    "youngzz",
    "Young",
    "Youngzz",
    "zz",
]

# 黑名单正则模式（可自由扩展）
blacklist_patterns = [
    r"^zz",  # 以 zz 开头
    r"^¡¡",  # 以 ¡¡ 开头
    r"^[_\-]+",  # 以 _ 或 - 开头
    r"^90",  # 以 _ 或 - 开头
    r"^\d+$",  # 纯数字
    r"^11190",  # 纯数字
    r"[\^\*%]",  # 含有 ^
    r"\s",  # 含有空白字符
    r"¡9",
    r"aa",  # 含有 aa
    r"cc",
    r"dd",
    r"ee",
    r"ff",
    r"gg",
    r"hh",
    r"ii",
    r"jj",
    r"kk",
    r"ll",
    r"mm",
    r"nn",
    r"oo",
    r"pp",
    r"qq",
    r"rr",
    r"ss",
    r"tt",
    r"uu",
    r"vv",
    r"ww",
    r"xx",
    r"yyy",
    r"zzz",
    r"1111",
    r"1239",
    r"9090",
    r"[jk]",  # 含有 j 或 k
    r"[\\/]",  # 包含 \ 或 /
    r"[<>]",  # 含有 < 或 >
    r"\.\.",  # 含有 ..
]

len_max = 16


def is_invalid(s: str) -> bool:
    return any(re.search(pat, s) for pat in blacklist_patterns)


def generate_passwords(n=1_000):
    results = set()
    chars = string.ascii_lowercase
    rng = np.random.default_rng()
    while len(results) < n:
        pwd_parts = []

        # 先放入一个必选子串
        pwd_parts.append(rng.choice(list(required_substrings)))

        # 随机目标长度 (至少等于第一个子串的长度)
        min_len = sum(len(p) for p in pwd_parts)
        target_len = rng.integers(min_len, len_max + 1)

        # 逐个追加，保持顺序
        while sum(len(p) for p in pwd_parts) < target_len:
            if rng.random() < 0.7:
                pwd_parts.append(rng.choice(chars))  # 多数情况添加单字符
            else:
                pwd_parts.append(
                    rng.choice(list(required_substrings))
                )  # 偶尔再加一个必选子串

            # 截断到目标长度
            total_len = sum(len(p) for p in pwd_parts)
            if total_len > target_len:
                pwd_parts = ["".join(pwd_parts)[:target_len]]
                break

        pwd = "".join(pwd_parts)

        if not is_invalid(pwd) and 1 <= len(pwd) <= len_max:
            results.add(pwd)

    return sorted(results)


if __name__ == "__main__":
    pwds = generate_passwords(1_000_000)
    with open("passwords.txt", "w", encoding="utf-8") as f:
        f.writelines(p + "\n" for p in pwds)
