"""按 md5 重判作业 1/2 成绩：同班同作业内重复组只留 1 人，其余记 0。

- 判重键：仅 .md 文件的整文件 md5；作业 2 的 .css 不参与判重，只随同名 .md 同步改分数后缀。
- 保留者：mtime 早者优先，并列取学号最小者（ctime 是批量拷贝时间，不作判据）。
- 默认预演；``--apply`` 才改名、备份成绩表并回填。

用法::

    PYTHONIOENCODING=utf-8 python scripts/dedup_md5.py
    PYTHONIOENCODING=utf-8 python scripts/dedup_md5.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from fill_scores import fill_column

ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT / "2026-cv-成绩.xlsx"
REPORT = ROOT / "reports" / f"md5-dedup-{datetime.now():%Y%m%d}.json"
NAME_RE = re.compile(r"^(\d{2})-(\d+)-(.+)-(\d+)$")
# 作业1 的 01-2401143079-张奕 学号写错（表中张奕是 2401143049，3079 是梁永刚）。
# 不擅自改学号，但回填时跳过它，避免把 0 写进梁永刚的行。
MIS_ID = {(242, 1, "张奕"): 2401143079}


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def parse(path: Path) -> tuple[str, int, str, int] | None:
    m = NAME_RE.match(path.stem)
    if m is None:
        return None
    prefix, sid, name, score = m.groups()
    return prefix, int(sid), name, int(score)


def rename_with_retry(src: Path, dst: Path) -> None:
    for _ in range(5):
        try:
            os.replace(src, dst)
            return
        except OSError:
            pass
    os.replace(src, dst)


def collect_groups(directory: Path) -> list[dict]:
    """返回按 md5 分组的重复信息（每组 >= 2 份）。"""
    buckets: dict[str, list[Path]] = {}
    for path in sorted(directory.glob("*.md")):
        buckets.setdefault(md5(path), []).append(path)
    groups = []
    for digest, paths in sorted(buckets.items()):
        if len(paths) < 2:
            continue
        ranked = sorted(
            paths,
            key=lambda p: (p.stat().st_mtime, parse(p)[1]),
        )
        groups.append(
            {
                "md5": digest,
                "kept": ranked[0].name,
                "zeroed": [p.name for p in ranked[1:]],
            }
        )
    return groups


def run(apply: bool) -> None:
    backup = XLSX.with_name(f"2026-cv-成绩.bak-md5-{datetime.now():%Y%m%d}.xlsx")
    report: dict = {"policy": "每班分别留1人：mtime 早者优先、并列取学号最小；仅按 md 判重", "tasks": {}}
    changes: list[tuple[Path, Path]] = []

    for klass in (241, 242):
        for task in (1, 2):
            directory = ROOT / f"智能B{klass}-{task:02d}"
            groups = collect_groups(directory)
            zeroed = {name for g in groups for name in g["zeroed"]}
            report["tasks"][f"{klass}-{task:02d}"] = {
                "groups": groups,
                "zeroed_count": len(zeroed),
            }

            for name in sorted(zeroed):
                path = directory / name
                parsed = parse(path)
                if parsed is None:
                    continue
                prefix, sid, student, _ = parsed
                new_stem = f"{prefix}-{sid}-{student}-0"
                changes.append((path, path.with_name(new_stem + ".md")))
                css = path.with_suffix(".css")
                if css.exists():
                    changes.append((css, css.with_name(new_stem + ".css")))

            scores: dict[int, tuple[str, int]] = {}
            skipped: list[str] = []
            for path in sorted(directory.glob("*.md")):
                parsed = parse(path)
                if parsed is None:
                    skipped.append(path.name)
                    continue
                _, sid, student, score = parsed
                if MIS_ID.get((klass, task, student)) == sid:
                    skipped.append(f"{path.name}（学号错，回填跳过）")
                    continue
                new_score = 0 if path.name in zeroed else score
                scores[sid] = (student, new_score)
            report["tasks"][f"{klass}-{task:02d}"]["scores"] = {
                str(sid): value for sid, value in sorted(scores.items())
            }
            report["tasks"][f"{klass}-{task:02d}"]["skipped"] = skipped

            print(f"\n== 智能B{klass}-{task:02d} ==")
            print(f"重复组 {len(groups)}，归零 {len(zeroed)} 人")
            for g in groups:
                print(f"  {g['md5'][:8]}  留 {g['kept']}  归零 {', '.join(g['zeroed'])}")

    report["renames"] = [
        {"from": str(src.relative_to(ROOT)), "to": str(dst.relative_to(ROOT))}
        for src, dst in changes
    ]
    print(f"\n改名 {len(changes)} 个文件")

    if not apply:
        print("（预演，未写盘）")
        return

    shutil.copy2(XLSX, backup)
    for src, dst in changes:
        rename_with_retry(src, dst)
    for klass in (241, 242):
        for task in (1, 2):
            scores = {
                int(sid): (str(v[0]), int(v[1]))
                for sid, v in report["tasks"][f"{klass}-{task:02d}"]["scores"].items()
            }
            result = fill_column(
                XLSX, f"智能B{klass}", f"作业{task}", scores, backup=False, verbose=False
            )
            print(f"回填 {result.sheet} {result.column}：{result.filled} 条")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"备份：{backup.name}")
    print(f"报告：{REPORT.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="按 md5 重判作业 1/2 成绩")
    parser.add_argument("--apply", action="store_true", help="执行改名与回填（默认只预演）")
    run(parser.parse_args().apply)


if __name__ == "__main__":
    main()
