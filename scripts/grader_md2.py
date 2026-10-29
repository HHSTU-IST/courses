"""Markdown 作业 2 批改脚本（Markdown 进阶：链接 / 表情 / HTML / CSS）。

与 ``grader_md.py`` 的扣分制不同，作业 2 按 ``x-ai/md-02-task.md`` 的检查项
**给分**：
- 规则表外置于同目录 ``errors_md2.json``，每项含 name / score / scope / mode /
  patterns / note；score 为该项命中后的得分，全部命中合计 100 分；
- scope 指明检查对象：md / css / both；mode 默认 any（任一 pattern 命中即算），
  all 表示全部 pattern 都须命中（如 colspan 与 rowspan 缺一不可）；
- 同一名学生的 ``02-学号-姓名.md`` 与 ``02-学号-姓名.css`` 成对合并计分，
  两份文件名均改写为 ``{原名}-{得分}.{扩展名}``；
- 附加扣分（都在给分结果上再减，最低 0 分）：
  1. md 里``<link>``引用的 css 学号与本人学号不一致（抄了同学的样式表）→
     ``CSS_ID_PENALTY``；引用里没有学号（仍是模板占位 ``02-学号-姓名.css`` 之类）
     无法比对，只提示不扣分；
  2. md 里根本没写 ``<link>``（样式表没挂上）→ ``NO_LINK_PENALTY``。

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
    base_score: int
    penalty: int
    missing: list[str]
    review: list[str]
    css_refs: list[str]
    css_mismatch: list[str]
    css_unknown: list[str]
    css_link_missing: bool
    detail: dict[str, ItemHit]


ITEMS_PATH = Path(__file__).with_name("errors_md2.json")

# 引用的 css 学号与本人学号不一致时的附加扣分（「抄了同学的样式表」）
CSS_ID_PENALTY = 30
# md 里完全没写 <link>、样式表根本没挂上时的附加扣分
NO_LINK_PENALTY = 30


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
ID_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")  # 10 位学号
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
# 各种「连字符」写法（U+2010…U+2013、减号、全角）统一成 ASCII '-'，
# 否则 02‑2401143010‑张凤佳.css 这类复制来的排版字符会漏判
DASH_MAP = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2212": "-",
        "\uff0d": "-",
    }
)


def strip_score_suffix(stem: str) -> str:
    """去掉上一次批改留下的 -{得分} 后缀，保证可重复执行。"""
    return SCORE_SUFFIX.sub("", stem)


def own_id(base: str) -> str | None:
    """从 ``02-学号-姓名`` 里取本人学号；取不到返回 None。"""
    m = ID_RE.search(base)
    return m.group(1) if m else None


def css_refs(md_text: str) -> list[str]:
    """取出 md 中 ``<link href=…>`` 引用的 css 文件名。

    去掉 ./ 前缀，按出现顺序去重。
    """
    refs: list[str] = []
    for tag in LINK_TAG_RE.findall(md_text.translate(DASH_MAP)):
        for href in HREF_RE.findall(tag):
            name = href.strip().split("?")[0].split("#")[0]
            if name.lower().endswith(".css"):
                name = name.removeprefix("./")
                if name not in refs:
                    refs.append(name)
    return refs


def css_id_mismatch(
    md_text: str, own: str | None
) -> tuple[list[str], list[str], list[str]]:
    """比对 md 引用的 css 学号与本人学号。

    返回 (全部引用, 学号不一致的引用, 无法判定学号的引用)。第三个列表是仍写着
    ``02-学号-姓名.css`` 这类模板占位、或文件名里没有学号的引用 —— 无从比较，只提示。
    """
    refs = css_refs(md_text)
    mismatch: list[str] = []
    unknown: list[str] = []
    for ref in refs:
        ref_id = ID_RE.search(Path(ref).name)
        if ref_id is None or own is None:
            unknown.append(ref)
        elif ref_id.group(1) != own:
            mismatch.append(ref)
    return refs, mismatch, unknown


def pattern_lines(pattern: str, text: str) -> list[int]:
    """返回 pattern 在 text 中命中的行号列表。"""
    return [
        text.count("\n", 0, m.start()) + 1
        for m in re.finditer(pattern, text, re.MULTILINE)
    ]


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


def collect(target: Path) -> tuple[dict[str, dict[str, Path]], list[Path], list[str]]:
    """按 02-学号-姓名 前缀配对 md 与 css。

    返回 (配对表, 无法识别的文件, 同一学号有多份提交的 base)。同一 base 出现两份
    同名提交（如先后留下 -100 与 -90）时不猜哪份是正本，整组跳过交人工处理，
    否则改名会互相覆盖。
    """
    groups: dict[str, dict[str, Path]] = {}
    stray: list[Path] = []
    duplicated: list[str] = []
    for path in sorted(target.iterdir()):
        if not path.is_file() or path.suffix not in {".md", ".css"}:
            continue
        base = strip_score_suffix(path.stem)
        if not NAME_RE.match(base):
            stray.append(path)
            continue
        ext = path.suffix.lstrip(".")
        slots = groups.setdefault(base, {})
        if ext in slots:
            if base not in duplicated:
                duplicated.append(base)
            continue
        slots[ext] = path
    for base in duplicated:
        del groups[base]
    return groups, stray, duplicated


def process(base: str, pair: dict[str, Path], apply: bool) -> FileResult:
    """批改一名学生：md 与 css 合并计分，再按附加规则扣分，并（可选）改名。"""
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
    base_score = sum(item.score for item in ITEMS if item.name in detail)

    own = own_id(base)
    refs, mismatch, unknown = css_id_mismatch(texts["md"], own)
    no_link = LINK_TAG_RE.search(texts["md"]) is None  # 根本没写 <link>，样式表没挂上
    cuts = [
        cut
        for cut, hit in ((NO_LINK_PENALTY, no_link), (CSS_ID_PENALTY, bool(mismatch)))
        if hit
    ]
    penalty = sum(cuts)
    score = max(0, base_score - penalty)  # 在现值上再减，最低 0 分

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
        file=base,
        score=score,
        base_score=base_score,
        penalty=penalty,
        missing=missing,
        review=review,
        css_refs=refs,
        css_mismatch=mismatch,
        css_unknown=unknown,
        css_link_missing=no_link,
        detail=detail,
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
    groups, stray, duplicated = collect(target)
    if not groups:
        raise SystemExit(f"目录中没有符合 02-学号-姓名 命名的 md/css 文件: {target}")
    for path in stray:
        print(f"警告：无法识别命名，跳过 {path.name}")
    for base in duplicated:
        print(f"警告：{base} 存在多份同名提交，已跳过，请人工保留一份后重跑")

    # 缺文件 / 空文件检查放在改名前做，避免引用已被改名的旧路径
    for base, pair in groups.items():
        if "md" not in pair or "css" not in pair:
            missing_ext = "css" if "md" in pair else "md"
            print(f"警告：{base} 缺少 {missing_ext} 文件，相关检查项按 0 分计")
        for scope, path in pair.items():
            if path.stat().st_size == 0:
                print(f"警告：{base} 的 {scope} 文件为空文件")

    apply = not args.dry_run
    out_dir = target / args.out if args.report else None
    results: list[FileResult] = [
        process(base, pair, apply) for base, pair in groups.items()
    ]

    width = max(len(r["file"]) for r in results)
    print(f"\n{'文件'.ljust(width)}  得分  扣分  缺失项")
    print("-" * (width + 46))
    for r in results:
        missing = "、".join(r["missing"]) or "无（满分）"
        cut = f"-{r['penalty']}" if r["penalty"] else ""
        print(f"{r['file'].ljust(width)}  {r['score']:>4}  {cut:>4}  {missing}")

    for r in results:
        if not r["missing"] and not r["review"] and not r["penalty"]:
            continue
        parts = [f"得分 {r['score']}"]
        if r["missing"]:
            lost = sum(i.score for i in ITEMS if i.name in r["missing"])
            parts.append(f"缺 {len(r['missing'])} 项失 {lost} 分")
        if r["css_link_missing"]:
            parts.append(f"未写 <link> 扣 {NO_LINK_PENALTY} 分")
        if r["css_mismatch"]:
            parts.append(f"css 学号不一致扣 {CSS_ID_PENALTY} 分")
        if r["penalty"]:
            parts.append(f"给分 {r['base_score']}")
        print(f"\n[{r['file']}]  {'，'.join(parts)}")
        for name in r["missing"]:
            item = next(i for i in ITEMS if i.name == name)
            print(f"  -{item.score} 分  {name}：{item.note}")
        if r["css_link_missing"]:
            print(f"  -{NO_LINK_PENALTY} 分  md 里没有 <link>，样式表未挂上")
        if r["css_mismatch"]:
            own = own_id(r["file"]) or "?"
            print(
                f"  -{CSS_ID_PENALTY} 分  引用的 css 学号与本人 {own} 不一致："
                f"{'、'.join(r['css_mismatch'])}"
            )
        if r["review"]:
            print(f"  命中但需人工复核：{'、'.join(r['review'])}")
        if r["css_unknown"]:
            print(f"  提示：css 引用无学号，未参与比对：{'、'.join(r['css_unknown'])}")

    average = round(sum(r["score"] for r in results) / len(results), 2)
    penalized = [r for r in results if r["penalty"]]
    no_link = [r for r in results if r["css_link_missing"]]
    mismatched = [r for r in results if r["css_mismatch"]]
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary: dict[str, object] = {
            "total": len(results),
            "full_score": FULL_SCORE,
            "average": average,
            "applied": apply,
            "css_id_penalty": CSS_ID_PENALTY,
            "no_link_penalty": NO_LINK_PENALTY,
            "penalized_count": len(penalized),
            "css_link_missing_count": len(no_link),
            "css_mismatch_count": len(mismatched),
            "skipped_duplicated": duplicated,
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
        f"，扣分 {len(penalized)} 人"
        f"（未写 <link> {len(no_link)} 人、css 学号不一致 {len(mismatched)} 人）"
        f"{'' if apply else '（dry-run，未改名）'}"
    )


if __name__ == "__main__":
    main()
