#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批改 ipynb 作业：基于 ``scripts/errors_ipynb.json`` 给 notebook 打分。

评分模型（与 ``scripts/grader.ipynb`` 完全一致）：

* 每份作业满分 ``INIT_SCORE``（默认 100）；
* 只拼接 **code cell** 源码（含注释；markdown 不计入）；
* ``penalties``：子串 **出现** 在代码中则扣分（坏味道，如 ``!pip install`` / ``sklearn``）；
* ``goals``：子串 **缺失** 则扣分（应当出现的 API，如 ``cv2.circle`` / ``plt.subplots``）；
* 最终分 ``= max(0, INIT_SCORE - 违规扣分之和)``。

规则表 ``errors_ipynb.json`` 形如 ``{key: {pattern: 分值}}``。按目录名前缀判定课程：

* ``计科*``            → goals=``ipynb+m{exp}``                      penalties=``ipynb-``
* ``物联网*`` / ``智能*``（CV/OpenCV）→ goals=``ipynb+v`` + ``ipynb+v{exp}``  penalties=``ipynb-`` + ``ipynb+v-``

``exp``（实验号）取自目录名结尾的实验号，例如 ``智能B241实验3`` → ``3``。

用法::

    python scripts/grader_ipynb.py 智能B241实验3              # 预演：打印得分表，不改名
    python scripts/grader_ipynb.py 智能B241实验3 --apply      # 按分数重命名为 {..}-{score}.ipynb
    python scripts/grader_ipynb.py 智能B241实验3 --report     # 额外写出 reports/summary.json
    python scripts/grader_ipynb.py 智能B241实验3 --fill       # 分数写入成绩表副本（不动原表）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INIT_SCORE = 100
RULES_PATH = Path(__file__).with_name("errors_ipynb.json")

# 课程前缀 -> 规则族
ML_PREFIXES = ("计科",)
CV_PREFIXES = ("物联网", "智能")
# 课程前缀 -> 成绩表文件名（供 --fill 使用）
SCORE_FILE_BY_PREFIX = {"计科": "2026-ml-成绩.xlsx", "物联网": "2026-cv-成绩.xlsx", "智能": "2026-cv-成绩.xlsx"}


class Result(TypedDict):
    """单份作业的批改结果。"""

    file: str
    student_id: str
    name: str
    score: int
    missing_goals: list[str]
    hit_penalties: list[str]


@dataclass
class RuleSet:
    """合并后的规则集：目标（缺失扣分）与罚分（出现扣分）。"""

    goals: dict[str, int] = field(default_factory=dict)
    penalties: dict[str, int] = field(default_factory=dict)


def load_cfg(path: Path = RULES_PATH) -> dict:
    """加载规则表；缺失或格式错误直接终止。"""
    if not path.exists():
        raise SystemExit(f"找不到规则文件: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"规则文件格式错误，应为对象: {path}")
    return data


def extract_exp(folder: str, files: list[Path]) -> int:
    """解析实验号：优先目录名（实验3 / 结尾数字），退化到 notebook 文件名前缀（03-...）。"""
    m = re.search(r"实验\s*(\d+)", folder) or re.search(r"(\d+)\s*$", folder)
    if m:
        return int(m.group(1))
    for p in files:
        m2 = re.match(r"(\d+)", p.name)
        if m2:
            return int(m2.group(1))
    raise SystemExit(f"无法从目录名或文件名解析实验号: {folder}")


def is_cv(folder: str) -> bool:
    return folder.startswith(CV_PREFIXES)


def resolve_rules(cfg: dict, folder: str, exp: int) -> RuleSet:
    """按课程与前缀合并 base + 分章 goals、base + 专属 penalties；缺失键一律按空处理，避免 None 崩溃。"""
    goals: dict[str, int] = {}
    penalties: dict[str, int] = dict(cfg.get("ipynb-") or {})

    if folder.startswith(ML_PREFIXES):
        goals.update(cfg.get(f"ipynb+m{exp}") or {})
    elif is_cv(folder):
        goals.update(cfg.get("ipynb+v") or {})          # CV 通用目标
        goals.update(cfg.get(f"ipynb+v{exp}") or {})    # 本章专属目标
        penalties.update(cfg.get("ipynb+v-") or {})     # CV 专属罚分（禁 sklearn）
    else:
        print(f"⚠ 目录前缀未匹配已知课程（计科/物联网/智能），仅套用通用罚分: {folder}")

    return RuleSet(goals=goals, penalties=penalties)


def code_of(nb: dict) -> str:
    """仅拼接 code cell 源码（list 或 str 兼容）。"""
    parts = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", [])
        parts.append("".join(src) if isinstance(src, list) else str(src))
    return "".join(parts)


def parse_name(path: Path) -> tuple[str, str, str]:
    """文件名形如 ``03-2401143005-杨佳雪.ipynb`` → (实验号, 学号, 姓名)；容错缺列。"""
    stem = strip_score_suffix(path.stem)
    items = stem.split("-")
    task = items[0] if len(items) >= 1 else ""
    sid = items[1] if len(items) >= 2 else ""
    name = items[2] if len(items) >= 3 else (items[-1] if len(items) >= 2 else "")
    return task, sid, name


def strip_score_suffix(stem: str) -> str:
    """去掉上一次批改留下的 ``-{得分}`` 后缀，保证可重复执行。"""
    return re.sub(r"-\d{1,3}$", "", stem)


def grade_file(path: Path, rules: RuleSet, init_score: int = INIT_SCORE) -> Result:
    """批改单个 notebook，返回结构化结果。"""
    nb = json.loads(path.read_text(encoding="utf-8"))
    code = code_of(nb)

    violations = 0
    hit_penalties: list[str] = []
    for pattern, penalty in rules.penalties.items():
        if pattern in code:
            violations += penalty
            hit_penalties.append(pattern)

    missing_goals: list[str] = []
    for pattern, goal in rules.goals.items():
        if pattern not in code:
            violations += goal
            missing_goals.append(pattern)

    score = max(0, init_score - violations)
    _task, sid, name = parse_name(path)
    return Result(
        file=path.name,
        student_id=sid,
        name=name,
        score=score,
        missing_goals=missing_goals,
        hit_penalties=hit_penalties,
    )


def rename_by_score(path: Path, score: int) -> Path:
    """把 ``{base}.ipynb`` 改名为 ``{base}-{score}.ipynb``（幂等：先剥离旧分数后缀）。"""
    base = strip_score_suffix(path.stem)
    target = path.with_name(f"{base}-{score}.ipynb")
    if target != path:
        if target.exists():
            raise FileExistsError(f"目标文件已存在: {target.name}")
        path.rename(target)
    return target


def fill_scores(results: list[Result], folder: str, exp: int, repo_root: Path, out_dir: Path) -> Path:
    """把分数写入成绩表 **副本**（原表不动）。定位表头中含 ``作业{exp}`` 的列、含 ``学号`` 的列。"""
    prefix = next((p for p in SCORE_FILE_BY_PREFIX if folder.startswith(p)), None)
    if prefix is None:
        raise SystemExit(f"目录前缀无法确定成绩表: {folder}")
    src = repo_root / SCORE_FILE_BY_PREFIX[prefix]
    if not src.exists():
        raise SystemExit(f"找不到成绩表: {src}")
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("需要 openpyxl 才能 --fill：pip install openpyxl")

    sheet_name = re.sub(r"实验\s*\d+\s*$", "", folder)
    wb = openpyxl.load_workbook(src)
    if sheet_name not in wb.sheetnames:
        raise SystemExit(f"成绩表中无工作表 {sheet_name!r}，现有: {wb.sheetnames}")
    ws = wb[sheet_name]

    header_row = score_col = id_col = None
    for r in range(1, min(ws.max_row, 12) + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str):
                s = v.strip()
                if s == f"作业{exp}" and score_col is None:
                    header_row, score_col = r, c
                if "学号" in s and id_col is None:
                    id_col, header_row = c, min(header_row or r, r)
    if score_col is None or id_col is None:
        raise SystemExit(f"在 {sheet_name} 前 12 行未找到 '作业{exp}' 或 '学号' 列")

    by_id = {r["student_id"]: r["score"] for r in results if r["student_id"].isdigit()}
    filled = 0
    for r in range(header_row + 1, ws.max_row + 1):
        sid = ws.cell(r, id_col).value
        key = str(int(sid)) if isinstance(sid, (int, float)) else str(sid).strip()
        if key in by_id:
            ws.cell(r, score_col).value = by_id[key]
            filled += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sheet_name}-作业{exp}-已填分.xlsx"
    wb.save(out_path)
    print(f"已填 {filled}/{len(by_id)} 名到副本: {out_path}（列 '作业{exp}'，原表未改动）")
    return out_path


def esc(pattern: str) -> str:
    """把规则里的换行/制表符转义成可见形式，避免在表格中把一行拆成多行。"""
    return pattern.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")


def print_table(results: list[Result], show_detail: bool = True) -> None:
    width = max([len(r["name"] + r["student_id"]) for r in results] + [8])
    print(f"{'学号-姓名'.ljust(width)}  {'得分':>4}  缺失目标 / 命中罚分")
    print("-" * (width + 50))
    for r in sorted(results, key=lambda x: x["student_id"]):
        tags = "、".join([esc(p) for p in r["missing_goals"]] + [f"⚠{esc(p)}" for p in r["hit_penalties"]]) or "无"
        print(f"{(r['student_id'] + '-' + r['name']).ljust(width)}  {r['score']:>4}  {tags}")
    avg = round(sum(r["score"] for r in results) / len(results), 2)
    print(f"\n共 {len(results)} 份，平均 {avg} 分，满分 {sum(1 for r in results if r['score'] == INIT_SCORE)} 份")


def main() -> None:
    parser = argparse.ArgumentParser(description="基于 errors_ipynb.json 批改 ipynb 作业")
    parser.add_argument("target", nargs="?", default="智能B241实验3", help="作业目录，默认 智能B241实验3")
    parser.add_argument("--apply", action="store_true", help="按分数重命名 notebook（默认只预演不改名）")
    parser.add_argument("--report", action="store_true", help="写出 reports/summary.json")
    parser.add_argument("--fill", action="store_true", help="分数写入成绩表副本")
    parser.add_argument("--quiet", action="store_true", help="只打印汇总表，不逐份列出缺失项")
    args = parser.parse_args()

    cfg = load_cfg()
    target = Path(args.target)
    if not target.is_dir():
        raise SystemExit(f"目录不存在: {target.resolve()}")
    files = sorted(target.glob("*.ipynb"))
    if not files:
        raise SystemExit(f"目录中没有 ipynb 文件: {target}")

    exp = extract_exp(target.name, files)
    rules = resolve_rules(cfg, target.name, exp)
    print(f"目录: {target}  |  实验号: {exp}  |  课程族: {'CV' if is_cv(target.name) else ('ML' if target.name.startswith(ML_PREFIXES) else '?')}")
    print(f"目标数: {len(rules.goals)}  罚分规则数: {len(rules.penalties)}\n")

    results = [grade_file(p, rules) for p in files]

    if args.apply:
        for p, r in zip(files, results):
            r["renamed"] = rename_by_score(p, r["score"]).name  # type: ignore[typeddict-item]
        print("已按分数重命名 notebook。\n")
    else:
        print("（预演模式，未改名；加 --apply 才会重命名）\n")

    print_table(results, show_detail=not args.quiet)

    repo_root = Path(__file__).resolve().parent.parent
    reports_dir = repo_root / "reports" / target.name
    if args.report:
        reports_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "folder": target.name,
            "exp": exp,
            "course": "CV" if is_cv(target.name) else "ML",
            "init_score": INIT_SCORE,
            "count": len(results),
            "average": round(sum(r["score"] for r in results) / len(results), 2),
            "files": results,
        }
        (reports_dir / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n报告: {reports_dir / 'summary.json'}")

    if args.fill:
        fill_scores(results, target.name, exp, repo_root, reports_dir)


if __name__ == "__main__":
    main()
