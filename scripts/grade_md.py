"""Markdown 作业批改脚本。

规则：
- 每份作业起始 100 分；
- 每命中一类语法错误扣 5 分，同类错误多次出现只扣一次；
- 命中结果写入 json 文件，key 为错误语法的正则表达式，value 为扣除分值；
- 文件名改为 ``{原文件名}-{得分}.md``。

用法：
    python scripts/grade_md.py 智能B241-01            # 预演，只打印错误与扣分
    python scripts/grade_md.py 智能B241-01 --apply    # 改名，不改报告
    python scripts/grade_md.py 智能B241-01 --report   # 额外写出 json 报告

默认不落盘：所有信息只打印到终端；只有显式给出 ``--report`` 才写
``reports/`` 下的逐份 json、``summary.json`` 与 ``errors.json``。

说明：围栏代码块内部先被等长空白遮蔽，再执行行级规则，
避免把代码里的 ``#`` 注释、``>``、缩进误判为 Markdown 语法错误。
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


# 规则表：pattern 即 json 中的 key
RULES: tuple[Rule, ...] = (
    Rule(
        "标题缺空格",
        r"^#{1,6}[^#\s]",
        "ATX 标题的 # 与标题文字之间必须有空格，否则 # 被当作普通字符",
    ),
    Rule(
        "标题未独占一行",
        r"[^\n\s#]#{2,6}[ \t]+\S",
        "标题标记必须位于行首；与上一行正文粘连时不会被解析为标题",
    ),
    Rule(
        "有序列表缺空格",
        r"^[ \t]*\d{1,9}[.)][^\s\d]",
        "有序列表标记 1. 之后必须有空格，否则整行退化为普通段落",
    ),
    Rule(
        "无序列表缺空格",
        r"^[ \t]*[-+](?![ \t\d+-])\S",
        "无序列表标记 - 或 + 之后必须有空格",
    ),
    Rule(
        "正文误用四空格缩进",
        r"^ {4,}(?![ \t]*(?:[-*+]|\d+[.)])[ \t])\S",
        "行首 4 个及以上空格会被解析为代码块，普通段落应顶格书写",
    ),
    Rule(
        "代码围栏未闭合",
        r"^```[^\n]*$",
        "起始围栏缺少配对的结束围栏，其后全文被吞进代码块",
    ),
    Rule(
        "裸语言名代替围栏",
        r"^(?:python|PYTHON|Python|java|JAVA|bash|BASH|sql|SQL|"
        r"javascript|JavaScript|cpp|C\+\+|HTML|css)[ \t]*$",
        "语言名必须写在 ``` 之后作为围栏信息串，不能单独占一行",
    ),
    Rule(
        "表格分隔行冒号非法",
        r"^(?=[^\n]*::)[ \t]*\|?[ \t:|-]*-[ \t:|-]*\|?[ \t]*$",
        "分隔行单元格只允许 :-- / --: / :--: 三种对齐写法，出现 :: 即非法",
    ),
    Rule(
        "行间公式重复嵌套",
        r"\$\$[ \t]*\\\[|\\\][ \t]*\$\$",
        "$$ 已经承担行间公式定界符，内部不得再套 \\[ \\]",
        raw=True,
    ),
    Rule(
        "强调符内侧有空格",
        r"(?:(?<=[ \t])|^)(?:\*\*|~~|__)[ \t]\S[^\n]*?(?:\*\*|~~|__)"
        r"|(?:(?<=[ \t])|^)(?:\*\*|~~|__)\S[^\n]*?[ \t](?:\*\*|~~|__)",
        "强调符（**, ~~）与文字之间不得有空格，否则不渲染或渲染残缺",
    ),
    Rule(
        "强调符未成对",
        r"^(?:[^*\n]*\*\*[^*\n]*\*\*)*[^*\n]*\*\*[^*\n]*$",
        "单行内加粗标记 ** 个数为奇数，加粗无法闭合",
    ),
    Rule(
        "行内代码反引号未配对",
        r"^(?!```)(?:[^`\n]*`[^`\n]*`)*[^`\n]*`[^`\n]*$",
        "单行内反引号个数为奇数，行内代码无法闭合",
    ),
    Rule(
        "图片语法残缺", r"^![ \t]*$", "孤立感叹号，通常是 ![](url) 图片语法写坏后的残留"
    ),
)

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
    parser.add_argument("--apply", action="store_true", help="实际改名（默认仅预演）")
    parser.add_argument(
        "--report", action="store_true", help="额外写出 json 报告（默认只打印）"
    )
    parser.add_argument("--out", default="reports", help="报告子目录名，默认 reports")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    files = sorted(p for p in target.glob("*.md") if p.is_file())
    if not files:
        raise SystemExit(f"目录中没有 md 文件: {target}")

    out_dir = target / args.out if args.report else None
    results: list[FileResult] = [process(p, args.apply, out_dir) for p in files]

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
            "applied": args.apply,
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
        f"{'' if args.apply else '（预演，未改名）'}"
    )


if __name__ == "__main__":
    main()
