"""Markdown 作业 2 批改脚本（Markdown 进阶：链接 / 表情 / HTML / CSS）。

与 ``grader_md.py`` 的扣分制不同，作业 2 按 ``x-ai/md-02-task.md`` 的检查项
**给分**：
- 规则表外置于同目录 ``errors_md2.json``，每项含 name / score / scope / mode /
  patterns / note；score 为该项命中后的得分，全部命中合计 100 分；
- scope 指明检查对象：md / css / both；mode 默认 any（任一 pattern 命中即算），
  all 表示全部 pattern 都须命中（如 colspan 与 rowspan 缺一不可）；
- 同一名学生的 ``02-学号-姓名.md`` 与 ``02-学号-姓名.css`` 成对合并计分，
  两份文件名均改写为 ``{原名}-{得分}.{扩展名}``。

用法：
    python scripts/grader_md2.py 智能B241-02            # 直接改名，并打印命中与缺失
    python scripts/grader_md2.py 智能B241-02 --dry-run  # 只预演，不改名
    python scripts/grader_md2.py 智能B241-02 --report   # 额外写出 json 报告
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from grader_md import mask_code  # 复用代码块遮蔽，避免示例代码被误判

FULL_SCORE = 100


@dataclass(frozen=True)
class Item:
    """一条给分检查项。"""

    name: str
    score: int
    scope: str  # md / css / both
    patterns: tuple[str, ...]
    mode: str  # any / all
    note: str


class ItemHit(TypedDict):
    """单项命中记录：按文件区分行号。"""

    score: int
    lines: dict[str, list[int]]


class FileResult(TypedDict):
    """单个学生的批改结果。"""

    file: str
    score: int
    missing: list[str]
    review: list[str]
    detail: dict[str, ItemHit]


ITEMS_PATH = Path(__file__).with_name("errors_md2.json")


def load_items(path: Path = ITEMS_PATH) -> tuple[Item, ...]:
    """从 json 规则表读取检查项；增删改检查项只需改 json。"""
    data: object = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("items") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise SystemExit(f"规则文件缺少非空 items 数组: {path}")

    items: list[Item] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(f"检查项条目必须是对象: {entry!r}")
        name, score = entry.get("name"), entry.get("score")
        patterns = entry.get("patterns")
        if not isinstance(name, str) or not isinstance(score, int):
            raise SystemExit(f"检查项缺少 name 或 score: {entry!r}")
        if not isinstance(patterns, list) or not all(
            isinstance(p, str) for p in patterns
        ):
            raise SystemExit(f"检查项 patterns 必须是非空字符串数组: {name!r}")
        scope = entry.get("scope", "md")
        if scope not in {"md", "css", "both"}:
            raise SystemExit(f"检查项 scope 非法: {name!r} -> {scope!r}")
        note = entry.get("note")
        items.append(
            Item(
                name=name,
                score=score,
                scope=scope,
                patterns=tuple(patterns),
                mode=entry.get("mode", "any"),
                note=note if isinstance(note, str) else "",
            )
        )
    return tuple(items)


ITEMS: tuple[Item, ...] = load_items()

SCORE_SUFFIX = re.compile(r"-\d{1,3}$")
NAME_RE = re.compile(r"^\d{2}-\d+-")  # 02-学号-姓名


def strip_score_suffix(stem: str) -> str:
    """去掉上一次批改留下的 -{得分} 后缀，保证可重复执行。"""
    return SCORE_SUFFIX.sub("", stem)


def pattern_lines(pattern: str, text: str) -> list[int]:
    """返回 pattern 在 text 中命中的行号列表。"""
    return [text.count("\n", 0, m.start()) + 1 for m in re.finditer(pattern, text, re.MULTILINE)]


def eval_item(item: Item, texts: dict[str, str]) -> tuple[bool, dict[str, list[int]]]:
    """按 mode 组合各 pattern 的命中结果，返回 (是否命中, 行号明细)。"""
    matched: list[bool] = []
    lines: dict[str, list[int]] = {"md": [], "css": []}
    for pattern in item.patterns:
        pat_lines = {"md": [], "css": []}
        for scope, text in texts.items():
            if item.scope != "both" and scope != item.scope:
                continue
            pat_lines[scope] = pattern_lines(pattern, text)
        ok = bool(pat_lines["md"] or pat_lines["css"])
        matched.append(ok)
        if ok:
            lines["md"] += pat_lines["md"]
            lines["css"] += pat_lines["css"]
    hit = all(matched) if item.mode == "all" else any(matched)
    if not hit:
        return False, {}
    return True, {k: sorted(set(v)) for k, v in lines.items() if v}


def collect(target: Path) -> tuple[dict[str, dict[str, Path]], list[Path]]:
    """按 02-学号-姓名 前缀配对 md 与 css；返回 (配对表, 无法识别的文件)。"""
    groups: dict[str, dict[str, Path]] = {}
    stray: list[Path] = []
    for path in sorted(target.iterdir()):
        if not path.is_file() or path.suffix not in {".md", ".css"}:
            continue
        base = strip_score_suffix(path.stem)
        if not NAME_RE.match(base):
            stray.append(path)
            continue
        groups.setdefault(base, {})[path.suffix.lstrip(".")] = path
    return groups, stray


def process(base: str, pair: dict[str, Path], apply: bool) -> FileResult:
    """批改一名学生：md 与 css 合并计分，并（可选）同时改名两份文件。"""
    texts = {"md": "", "css": ""}
    for scope, path in pair.items():
        raw = path.read_text(encoding="utf-8-sig")
        texts[scope] = mask_code(raw) if scope == "md" else raw

    detail: dict[str, ItemHit] = {}
    missing: list[str] = []
    for item in ITEMS:
        hit, lines = eval_item(item, texts)
        if hit:
            detail[item.name] = ItemHit(score=item.score, lines=lines)
        else:
            missing.append(item.name)
    score = sum(item.score for item in ITEMS if item.name in detail)

    if apply:
        for path in pair.values():
            target = path.with_name(f"{base}-{score}{path.suffix}")
            if target != path:
                if target.exists():
                    raise FileExistsError(f"目标文件已存在: {target.name}")
                path.rename(target)

    # 命中了但标注需人工复核的检查项（note 中含「人工」「复核」）
    review = [
        item.name
        for item in ITEMS
        if item.name in detail and ("人工" in item.note or "复核" in item.note)
    ]
    return FileResult(
        file=base, score=score, missing=missing, review=review, detail=detail
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown 作业 2 批改（给分制）")
    parser.add_argument("target", help="作业目录，如 智能B241-02")
    parser.add_argument("--dry-run", action="store_true", help="只预演，不改名")
    parser.add_argument(
        "--report", action="store_true", help="额外写出 json 报告（默认只打印）"
    )
    parser.add_argument("--out", default="reports", help="报告子目录名，默认 reports")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    groups, stray = collect(target)
    if not groups:
        raise SystemExit(f"目录中没有符合 02-学号-姓名 命名的 md/css 文件: {target}")
    for path in stray:
        print(f"警告：无法识别命名，跳过 {path.name}")

    apply = not args.dry_run
    out_dir = target / args.out if args.report else None
    results: list[FileResult] = [
        process(base, pair, apply) for base, pair in groups.items()
    ]

    for base, pair in groups.items():
        if "md" not in pair or "css" not in pair:
            missing_ext = "css" if "md" in pair else "md"
            print(f"警告：{base} 缺少 {missing_ext} 文件，相关检查项按 0 分计")
        for scope, path in pair.items():
            if path.stat().st_size == 0:
                print(f"警告：{base} 的 {scope} 文件为空文件")

    width = max(len(r["file"]) for r in results)
    print(f"\n{'文件'.ljust(width)}  得分  缺失项")
    print("-" * (width + 40))
    for r in results:
        missing = "、".join(r["missing"]) or "无（满分）"
        print(f"{r['file'].ljust(width)}  {r['score']:>4}  {missing}")

    for r in results:
        if not r["missing"] and not r["review"]:
            continue
        parts = [f"得分 {r['score']}"]
        if r["missing"]:
            lost = sum(i.score for i in ITEMS if i.name in r["missing"])
            parts.append(f"缺 {len(r['missing'])} 项失 {lost} 分")
        print(f"\n[{r['file']}]  {'，'.join(parts)}")
        for name in r["missing"]:
            item = next(i for i in ITEMS if i.name == name)
            print(f"  -{item.score} 分  {name}：{item.note}")
        if r["review"]:
            print(f"  命中但需人工复核：{'、'.join(r['review'])}")

    average = round(sum(r["score"] for r in results) / len(results), 2)
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary: dict[str, object] = {
            "total": len(results),
            "full_score": FULL_SCORE,
            "average": average,
            "applied": apply,
            "files": results,
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        # 各检查项的全班命中统计，便于定位普遍薄弱点
        stat = [
            {
                "name": item.name,
                "score": item.score,
                "hit_count": sum(item.name in r["detail"] for r in results),
                "hit_rate": round(
                    sum(item.name in r["detail"] for r in results) / len(results), 4
                ),
            }
            for item in ITEMS
        ]
        (out_dir / "items.json").write_text(
            json.dumps(stat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n检查项命中统计见 {out_dir / 'items.json'}")

    print(
        f"\n共 {len(results)} 人，平均 {average} 分"
        f"{'' if apply else '（dry-run，未改名）'}"
    )


if __name__ == "__main__":
    main()
