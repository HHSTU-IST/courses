#!/usr/bin/env python3
"""按整文件 md5 查重 ipynb 作业（作业3/4）：重复组只留一份，其余归零。

复用 ``grader_ipynb`` 的署名优先查重引擎（署名作者 → 时间戳 → 文件名兜底），
判据为用户指定的**整文件 md5**（``--dedup-by file``）。``--apply`` 才改名、备份成绩表并回填。

用法::

    PYTHONIOENCODING=utf-8 python scripts/dedup_md5_ipynb.py
    PYTHONIOENCODING=utf-8 python scripts/dedup_md5_ipynb.py --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import openpyxl
from fill_scores import fill_column, find_header
from grader_ipynb import (
    apply_duplicate_policy,
    extract_exp,
    grade_file,
    load_cfg,
    print_duplicates,
    rename_by_score,
    resolve_rules,
)

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "2026-cv-成绩.xlsx"
REPORT = ROOT / "reports" / f"md5-dedup-ipynb-{datetime.now():%Y%m%d}.json"

# (目录, 班级, 作业号, 工作表名)
TARGETS = [
    ("智能B241-03", 241, 3, "智能B241"),
    ("智能B241-04", 241, 4, "智能B241"),
    ("智能B242-03", 242, 3, "智能B242"),
    ("智能B242-04", 242, 4, "智能B242"),
]
# 文件名学号写错：回填时按姓名纠正到表中真实学号，文件名保持原样
MIS_ID = {"240143073": 2401143073}  # 智能B242-04 梁静仪


def current_scores(sheet: str, exp: int) -> dict[int, object]:
    """读取成绩表中该作业列的当前值，用于预演对比。"""
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb[sheet]
    header_row, score_col = find_header(ws, f"作业{exp}")
    _, id_col = find_header(ws, "学号")
    out: dict[int, object] = {}
    for row in range(header_row + 1, ws.max_row + 1):
        sid = ws.cell(row, id_col).value
        if isinstance(sid, int):
            out[sid] = ws.cell(row, score_col).value
    wb.close()
    return out


def run(apply: bool) -> None:
    cfg = load_cfg()
    backup = XLSX.with_name(f"2026-cv-成绩.bak-md5ipynb-{datetime.now():%Y%m%d}.xlsx")
    report: dict = {
        "policy": "整文件 md5 分组；保留者：署名作者优先，否则时间戳(auto)，并列按文件名兜底；其余归零",
        "dedup_by": "file（整文件 md5）",
        "tasks": {},
    }
    renames: list[tuple[Path, Path]] = []

    for folder, _klass, exp, sheet in TARGETS:
        directory = ROOT / folder
        files = sorted(directory.glob("*.ipynb"))
        rules = resolve_rules(cfg, folder, extract_exp(folder, files))
        results = [grade_file(p, rules) for p in files]
        groups, time_key = apply_duplicate_policy(results, files, "auto", "file")

        print(f"\n=== {folder}（作业{exp}） 时间键={time_key} 文件={len(files)} ===")
        print_duplicates(groups, directory, time_key, "file")

        zeroed = [
            r["file"]
            for r in results
            if r["score"] == 0
            and (r["duplicate_of"] or r["dup_reason"] == "author-absent")
        ]
        scores: dict[int, tuple[str, int]] = {}
        notes: list[str] = []
        for r in results:
            sid = int(r["student_id"])
            if str(sid) in MIS_ID:
                notes.append(
                    f"{r['file']}: 学号 {sid} 表中不存在，按姓名纠正为 {MIS_ID[str(sid)]}（文件名不动）"
                )
                sid = MIS_ID[str(sid)]
            scores[sid] = (r["name"], r["score"])

        before = current_scores(sheet, exp)
        changes = [
            (sid, scores[sid][0], before.get(sid), scores[sid][1])
            for sid in sorted(scores)
            if before.get(sid) != scores[sid][1]
        ]
        print(f"归零 {len(zeroed)} 份；回填 {len(scores)} 条到 {sheet}!作业{exp}")
        if changes:
            print(f"分数变化 {len(changes)} 条（学号 姓名 旧→新）:")
            for sid, name, old, new in changes:
                print(f"  {sid} {name}: {old} → {new}")
        for n in notes:
            print(f"  ⚠ {n}")

        report["tasks"][folder] = {
            "sheet": sheet,
            "column": f"作业{exp}",
            "time_key": time_key,
            "groups": groups,
            "zeroed_count": len(zeroed),
            "zeroed_files": sorted(zeroed),
            "scores": {str(k): v for k, v in sorted(scores.items())},
            "changes": [
                {"sid": sid, "name": name, "old": old, "new": new}
                for sid, name, old, new in changes
            ],
            "notes": notes,
        }

        for p, r in zip(files, results):
            # 纯计算目标名，不在此处改名（改名统一放到写盘阶段，保证预演零副作用）
            target = p.with_name(
                f"{re.sub(r'-\d{1,3}$', '', p.stem)}-{r['score']}.ipynb"
            )
            if target != p:
                renames.append((p, target))

    report["renames"] = [
        {"from": str(src.relative_to(ROOT)), "to": str(dst.relative_to(ROOT))}
        for src, dst in renames
    ]
    print(f"\n共需改名 {len(renames)} 个文件")

    if not apply:
        print("（预演，未写盘；加 --apply 执行）")
        return

    shutil.copy2(XLSX, backup)
    for src, dst in renames:
        # 幂等：若上次中断前已改名，src 不再存在而 dst 已是目标，直接跳过
        if not src.exists() and dst.exists():
            continue
        if dst.exists():
            raise FileExistsError(f"目标文件已存在: {dst}")
        rename_by_score(src, int(dst.stem.rsplit("-", 1)[-1]))
    for folder, _klass, exp, sheet in TARGETS:
        scores = {
            int(k): (str(v[0]), int(v[1]))
            for k, v in report["tasks"][folder]["scores"].items()
        }
        result = fill_column(XLSX, sheet, f"作业{exp}", scores, backup=False, verbose=False)
        print(f"回填 {result.sheet}!{result.column}: {result.filled} 条")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"备份: {backup.name}")
    print(f"报告: {REPORT.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="按整文件 md5 查重 ipynb 作业并回填成绩表")
    parser.add_argument("--apply", action="store_true", help="执行改名与回填（默认只预演）")
    run(parser.parse_args().apply)


if __name__ == "__main__":
    main()
