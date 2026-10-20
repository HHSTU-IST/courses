"""Markdown 作业批改脚本。

规则：
- 每份作业起始 100 分；
- 每命中一类语法错误扣 5 分，同类错误多次出现只扣一次；
- 文件名改为 ``{原文件名}-{得分}.md``。

规则表外置于同目录的 ``errors_md.json``，每条含 name / pattern / note / raw：
    {"rules": [{"name": "标题缺空格", "pattern": "^#{1,6}[^#\\s]", "note": "...",
                "raw": false}]}
``raw`` 为 true 表示该规则匹配未遮蔽的原文（用于 ``$$`` 这类容器本身的语法）。

用法：
    python scripts/grader_md.py 智能B241-01            # 直接改名，并打印错误与扣分
    python scripts/grader_md.py 智能B241-01 --dry-run  # 只预演，不改名
    python scripts/grader_md.py 智能B241-01 --report   # 额外写出 json 报告
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

INIT_SCORE = 100
PENALTY = 5


class RuleHit(TypedDict):
    """单条规则的命中记录。"""

    pattern: str
    lines: list[int]
    note: str


class FileResult(TypedDict):
    """单份作业的批改结果。"""

    file: str
    score: int
    rules: list[str]
    detail: dict[str, RuleHit]


class ErrorEntry(TypedDict):
    """errors.json 中的一条错误语法。"""

    name: str
    score: int


@dataclass(frozen=True)
class Rule:
    """一条语法错误规则。"""

    name: str
    pattern: str
    note: str
    raw: bool = False


RULES_PATH = Path(__file__).with_name("errors_md.json")


def load_rules(path: Path = RULES_PATH) -> tuple[Rule, ...]:
    """从 json 规则表读取规则；增删改规则只需改 json。"""
    data: object = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("rules") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise SystemExit(f"规则文件格式错误，缺少 rules 数组: {path}")

    rules: list[Rule] = []
    for item in items:
        if not isinstance(item, dict):
            raise SystemExit(f"规则条目必须是对象: {item!r}")
        name, pattern = item.get("name"), item.get("pattern")
        if not isinstance(name, str) or not isinstance(pattern, str):
            raise SystemExit(f"规则缺少 name 或 pattern: {item!r}")
        note = item.get("note")
        rules.append(
            Rule(
                name=name,
                pattern=pattern,
                note=note if isinstance(note, str) else "",
                raw=bool(item.get("raw", False)),
            )
        )
    if not rules:
        raise SystemExit(f"规则文件为空: {path}")
    return tuple(rules)


RULES: tuple[Rule, ...] = load_rules()

FENCE_BLOCK = re.compile(r"^```[^\n]*\n(?:(?!^```)[\s\S])*^```[^\n]*$", re.MULTILINE)
MATH_BLOCK = re.compile(r"^[ \t]*\$\$[\s\S]*?\$\$", re.MULTILINE)


def unclosed_fence_lines(text: str) -> list[int]:
    """围栏行数为奇数时，最后一个围栏没有配对，视为未闭合。"""
    lines = [i for i, line in enumerate(text.split("\n"), 1) if line.startswith("```")]
    return [lines[-1]] if len(lines) % 2 else []


def _blank(match: re.Match[str]) -> str:
    """等长空白替换，保留字符偏移与行号。"""
    return re.sub(r"[^\n]", " ", match.group(0))


def mask_code(text: str) -> str:
    """遮蔽围栏代码块与行间公式，避免容器内部的符号被当作 Markdown 语法。"""
    return MATH_BLOCK.sub(_blank, FENCE_BLOCK.sub(_blank, text))


def strip_score_suffix(stem: str) -> str:
    """去掉上一次批改留下的 -{得分} 后缀，保证可重复执行。"""
    return re.sub(r"-\d{2,3}$", "", stem)


def grade_text(raw: str) -> dict[str, list[int]]:
    """返回 {命中的正则: [行号, ...]}。"""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    masked = mask_code(text)
    hits: dict[str, list[int]] = {}
    for rule in RULES:
        if rule.name == "代码围栏未闭合":
            lines = unclosed_fence_lines(text)
        else:
            source = text if rule.raw else masked
            lines = [
                source.count("\n", 0, m.start()) + 1
                for m in re.finditer(rule.pattern, source, re.MULTILINE)
            ]
        if lines:
            hits[rule.pattern] = sorted(set(lines))
    return hits


def process(path: Path, apply: bool, out_dir: Path | None) -> FileResult:
    """批改单个文件并（可选）改名；out_dir 非空时才写报告。"""
    raw = path.read_text(encoding="utf-8-sig")
    hits = grade_text(raw)
    score = max(0, INIT_SCORE - PENALTY * len(hits))

    base = strip_score_suffix(path.stem)
    target = path.with_name(f"{base}-{score}.md")
    if apply and target != path:
        if target.exists():
            raise FileExistsError(f"目标文件已存在: {target.name}")
        path.rename(target)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        report = {pattern: PENALTY for pattern in hits}
        (out_dir / f"{base}-{score}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    detail: dict[str, RuleHit] = {
        rule.name: RuleHit(
            pattern=rule.pattern, lines=hits[rule.pattern], note=rule.note
        )
        for rule in RULES
        if rule.pattern in hits
    }
    return FileResult(file=base, score=score, rules=list(detail), detail=detail)


def main() -> None:
    parser = argparse.ArgumentParser(description="Markdown 作业批改")
    parser.add_argument("target", help="作业目录，如 智能B241-01")
    parser.add_argument("--dry-run", action="store_true", help="只预演，不改名")
    parser.add_argument(
        "--report", action="store_true", help="额外写出 json 报告（默认只打印）"
    )
    parser.add_argument("--out", default="reports", help="报告子目录名，默认 reports")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    files = sorted(p for p in target.glob("*.md") if p.is_file())
    if not files:
        raise SystemExit(f"目录中没有 md 文件: {target}")

    apply = not args.dry_run
    out_dir = target / args.out if args.report else None
    results: list[FileResult] = [process(p, apply, out_dir) for p in files]

    width = max(len(r["file"]) for r in results)
    print(f"{'文件'.ljust(width)}  得分  命中规则")
    print("-" * (width + 40))
    for r in results:
        rules = "、".join(r["rules"]) or "无"
        print(f"{r['file'].ljust(width)}  {r['score']:>4}  {rules}")

    for r in results:
        if not r["detail"]:
            continue
        print(
            f"\n[{r['file']}]  得分 {r['score']}，共扣 {len(r['detail']) * PENALTY} 分"
        )
        for name, hit in r["detail"].items():
            shown = "、".join(str(n) for n in hit["lines"][:8])
            if len(hit["lines"]) > 8:
                shown += " …"
            print(f"  -{PENALTY} 分  {name}（{len(hit['lines'])} 处，第 {shown} 行）")

    average = round(sum(r["score"] for r in results) / len(results), 2)
    if out_dir is not None:
        summary: dict[str, object] = {
            "total": len(results),
            "init_score": INIT_SCORE,
            "penalty": PENALTY,
            "average": average,
            "applied": apply,
            "files": results,
        }
        (out_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        # 合并去重：key 为错误语法正则，value 记录错误名称与扣分，不含姓名学号
        merged: dict[str, ErrorEntry] = {
            rule.pattern: ErrorEntry(name=rule.name, score=PENALTY)
            for rule in RULES
            if any(rule.name in r["detail"] for r in results)
        }
        (out_dir / "errors.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"合并后错误语法 {len(merged)} 条，见 {out_dir / 'errors.json'}")

    print(
        f"\n共 {len(results)} 份，平均 {average} 分"
        f"{'' if apply else '（dry-run，未改名）'}"
    )


if __name__ == "__main__":
    main()
