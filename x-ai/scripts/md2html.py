#!/usr/bin/env python
"""Markdown -> 单文件 HTML 转换器。

基于 markdown-it-py（解析）+ Pygments（代码高亮）+ MathJax（公式渲染），
支持 GFM 表格/删除线、任务列表、GitHub 风格标注（> [!NOTE]）、行内/块级 LaTeX
公式、标题锚点，输出自带样式、可直接双击打开的单文件 HTML。

页面样式位于 ../styles/md2html.css，公式符号映射位于 unicode-math.json，
二者在生成时读取；Pygments 的高亮配色在运行时按需生成。

用法::

    micromamba run -n kaggle python scripts/md2html.py md-01-task.md
    micromamba run -n kaggle python scripts/md2html.py input.md -o out.html
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, cast

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict
from pygments import highlight as pygments_highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

# 渲染规则的签名：(tokens, idx, options, env) -> html
RenderRule = Callable[[Sequence[Token], int, OptionsDict, EnvType], str]

MATHJAX_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"

# 占位符：使用 Unicode 私用区字符，几乎不可能与正文冲突，且不会被 HTML 转义
PH_BEGIN = "\ue000"
PH_END = "\ue001"

# 公式中的 Unicode 符号 -> TeX 命令（提高渲染兼容性），见 load_unicode_math()
UNICODE_MATH_FILE = Path(__file__).resolve().parent / "unicode-math.json"

# 标注（Callout）的默认标题
CALLOUT_TITLES = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
}


# --------------------------------------------------------------------------- #
# 一、源码扫描：把代码块与公式替换为占位符，避免 Markdown 解析破坏其内容
# --------------------------------------------------------------------------- #
def _placeholder(index: int) -> str:
    return f"{PH_BEGIN}{index}{PH_END}"


def _tail_breaks(out: list[str]) -> int:
    """out 末尾连续换行的个数。"""
    count = 0
    for j in range(len(out) - 1, -1, -1):
        if out[j] == "\n":
            count += 1
        else:
            break
    return count


def _open_block(out: list[str]) -> None:
    """在写入块级占位符之前补齐空行，保证它能独占一段。"""
    if not out:
        return
    need = 2 - _tail_breaks(out)
    if need > 0:
        out.append("\n" * need)


def _close_block(out: list[str], src: str, pos: int) -> None:
    """在块级占位符之后补齐空行（若原文此处已有空行则不动）。"""
    lead = 0
    while pos + lead < len(src) and src[pos + lead] == "\n":
        lead += 1
    need = 2 - lead
    if need > 0:
        out.append("\n" * need)


def protect(src: str) -> tuple[str, list[tuple[str, str, str]]]:
    """将围栏代码块、行内代码、行内/块级公式抽出，返回 (遮罩文本, 片段列表)。"""
    slots: list[tuple[str, str, str]] = []  # (kind, info, body)
    out: list[str] = []
    i, n = 0, len(src)

    while i < n:
        ch = src[i]

        # 转义的 $ / ` 不当作定界符
        if ch == "\\" and i + 1 < n and src[i + 1] in {"$", "`"}:
            out.append(src[i : i + 2])
            i += 2
            continue

        at_line_start = i == 0 or src[i - 1] == "\n"

        # 1) 围栏代码块（必须在行首，且必须找到闭合围栏）
        if at_line_start and (m := re.match(r"(`{3,}|~{3,})([^\n]*)\n?", src[i:])):
            fence, info = m.group(1), m.group(2).strip()
            body_start = i + m.end()
            closing = re.search(
                r"^ {0,3}" + re.escape(fence) + r"[ \t]*$",
                src[body_start:],
                re.MULTILINE,
            )
            if closing:
                body_end = body_start + closing.start()
                slots.append(("fence", info, src[body_start:body_end]))
                _open_block(out)
                out.append(_placeholder(len(slots) - 1))
                end = body_start + closing.end()
                _close_block(out, src, end)
                i = end
                continue

        # 2) 行内代码
        if ch == "`":
            tick = re.match(r"`+", src[i:])
            if tick is None:  # 理论上不会发生：当前字符已是反引号
                out.append(ch)
                i += 1
                continue
            run = tick.group(0)
            closing = re.compile(r"(?<!`)" + re.escape(run) + r"(?!`)").search(
                src, i + len(run)
            )
            if closing:
                slots.append(("code", "", src[i + len(run) : closing.start()]))
                out.append(_placeholder(len(slots) - 1))
                i = closing.end()
                continue

        # 3) 公式
        if ch == "$":
            if src.startswith("$$", i):
                end = src.find("$$", i + 2)
                if end != -1:
                    slots.append(("math_block", "", src[i + 2 : end]))
                    _open_block(out)
                    out.append(_placeholder(len(slots) - 1))
                    tail = end + 2
                    _close_block(out, src, tail)
                    i = tail
                    continue
            else:
                end = src.find("$", i + 1)
                inner = src[i + 1 : end] if end != -1 else ""
                nxt = src[i + 1] if i + 1 < n else ""
                if (
                    end != -1
                    and nxt.strip()
                    and src[end - 1] != "\\"
                    and src[end - 1].strip()
                    and "\n" not in inner
                ):
                    slots.append(("math_inline", "", inner))
                    out.append(_placeholder(len(slots) - 1))
                    i = end + 1
                    continue

        out.append(ch)
        i += 1

    return "".join(out), slots


# --------------------------------------------------------------------------- #
# 二、占位符还原
# --------------------------------------------------------------------------- #
@cache
def load_unicode_math(path: Path | None = None) -> Mapping[str, str]:
    """读取 Unicode 符号到 TeX 命令的映射表。"""
    target = path or UNICODE_MATH_FILE
    if not target.is_file():
        raise FileNotFoundError(f"找不到符号映射表: {target}")
    with target.open(encoding="utf-8") as fp:
        data = json.load(fp)
    return dict(data)


def _normalize_tex(text: str, mapping: Mapping[str, str] | None = None) -> str:
    for uni, tex in (mapping if mapping is not None else load_unicode_math()).items():
        text = text.replace(uni, tex)
    return text.strip("\n")


def _highlight_code(code: str, lang: str) -> str:
    if lang:
        try:
            lexer = get_lexer_by_name(lang, ensurenl=False)
        except ClassNotFound:
            lexer = None
        if lexer is not None:
            # nowrap=True：由我们自己包 <pre>，便于统一控制样式
            return pygments_highlight(
                code, lexer, HtmlFormatter(nowrap=True, noclasses=False)
            )
    return html_lib.escape(code, quote=False)


def _render_slot(
    kind: str, info: str, body: str, mapping: Mapping[str, str] | None = None
) -> str:
    """把抽出的片段渲染为 HTML。"""
    if kind == "fence":
        lang = info.split()[0] if info else ""
        code = body.rstrip("\n")
        figure = '<figure class="code-block">'
        if lang:
            figure += (
                f'<figcaption class="code-lang">{html_lib.escape(lang)}</figcaption>'
            )
        figure += (
            f'<pre class="highlight"><code>{_highlight_code(code, lang)}</code></pre>'
        )
        return figure + "</figure>\n"

    if kind == "code":
        return f'<code class="inline-code">{html_lib.escape(body.strip(), quote=False)}</code>'

    if kind == "math_inline":
        tex = html_lib.escape(_normalize_tex(body, mapping), quote=False)
        return f'<span class="math math-inline">\\({tex}\\)</span>'

    if kind == "math_block":
        tex = html_lib.escape(_normalize_tex(body, mapping), quote=False)
        return f'<div class="math math-display">\\[{tex}\\]</div>\n'

    raise ValueError(f"未知片段类型: {kind}")


def restore(
    rendered: str,
    slots: list[tuple[str, str, str]],
    mapping: Mapping[str, str] | None = None,
) -> str:
    for idx, (kind, info, body) in enumerate(slots):
        frag = _render_slot(kind, info, body, mapping)
        ph = _placeholder(idx)
        # 独占段落的片段：连同外层的 <p> 一起替换，避免出现 <p><pre> 这类非法嵌套
        pattern = re.compile(r"<p[^>]*>\s*" + re.escape(ph) + r"\s*</p>\s*")
        rendered, count = pattern.subn(lambda _m, box=frag: box, rendered)
        if not count:
            rendered = rendered.replace(ph, frag)
    return rendered


# --------------------------------------------------------------------------- #
# 三、markdown-it 扩展：任务列表 / 标注 / 标题锚点
# --------------------------------------------------------------------------- #
_CALLOUT_RE = re.compile(r"^\[!([A-Za-z]+)\][ \t]*([^\n]*)")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+")


def _matching_close(
    tokens: list[Token], open_index: int, open_type: str, close_type: str
) -> int:
    level = 0
    for j in range(open_index, len(tokens)):
        if tokens[j].type == open_type:
            level += 1
        elif tokens[j].type == close_type:
            level -= 1
            if level == 0:
                return j
    return -1


def _token_text(token: Token) -> str:
    if token.children:
        return "".join(_token_text(child) for child in token.children)
    return token.content


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", text.strip().replace(" ", "-"))
    return slug.strip("-") or "section"


def callout_plugin(md: MarkdownIt) -> None:
    """`> [!NOTE] 标题` -> GitHub 风格标注块。"""

    def _rule(state) -> None:
        tokens = state.tokens
        drop: set[int] = set()
        for idx, token in enumerate(tokens):
            if token.type != "blockquote_open" or idx + 2 >= len(tokens):
                continue
            para_open, inline = tokens[idx + 1], tokens[idx + 2]
            if para_open.type != "paragraph_open" or inline.type != "inline":
                continue
            match = _CALLOUT_RE.match(inline.content)
            if not match:
                continue
            kind = match.group(1).lower()
            title = match.group(2).strip() or CALLOUT_TITLES.get(kind, kind.title())
            rest = inline.content[match.end() :].lstrip("\r\n")
            close = _matching_close(tokens, idx, "blockquote_open", "blockquote_close")
            if close < 0:
                continue

            token.meta = {"callout": kind, "title": title}
            tokens[close].meta = {"callout": kind}

            if rest.strip():
                inline.content = rest
            else:  # 只有标题、没有正文：移除空的段落
                drop.update({idx + 1, idx + 2, idx + 3})

        for j in sorted(drop, reverse=True):
            del tokens[j]

    # md.renderer 的静态类型是 RendererProtocol，实际默认是 RendererHTML
    renderer = cast("RendererHTML", md.renderer)
    # 未注册的 token 默认走 renderToken，因此取不到规则时回退到它
    open_rule = renderer.rules.get("blockquote_open") or renderer.renderToken
    close_rule = renderer.rules.get("blockquote_close") or renderer.renderToken

    def _render_open(
        tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        meta = tokens[idx].meta or {}
        kind = meta.get("callout")
        if not kind:
            return open_rule(tokens, idx, options, env)
        title = meta.get("title", CALLOUT_TITLES.get(kind, kind.title()))
        title_html = md.renderInline(str(title)).strip()
        kind_html = html_lib.escape(kind)
        # 保留源码 [!TYPE] 中的感叹号，渲染为标题前的圆形徽标
        icon = '<span class="markdown-alert-icon">!</span>'
        return (
            f'<aside class="markdown-alert markdown-alert-{kind_html}">'
            f'<p class="markdown-alert-title">{icon}{title_html}</p>\n'
        )

    def _render_close(
        tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        if (tokens[idx].meta or {}).get("callout"):
            return "</aside>\n"
        return close_rule(tokens, idx, options, env)

    md.core.ruler.after("block", "callouts", _rule)
    rules = cast("dict[str, Any]", renderer.rules)
    rules["blockquote_open"] = _render_open
    rules["blockquote_close"] = _render_close


def tasklist_plugin(md: MarkdownIt) -> None:
    """`- [ ] item` / `- [x] item` -> 复选框列表。"""

    def _rule(state) -> None:
        tokens = state.tokens
        for idx, token in enumerate(tokens):
            if token.type != "inline" or idx < 2 or not token.children:
                continue
            if tokens[idx - 1].type != "paragraph_open":
                continue
            if tokens[idx - 2].type != "list_item_open":
                continue
            first = token.children[0]
            if first.type != "text":
                continue
            match = _TASK_RE.match(first.content)
            if not match:
                continue
            first.content = first.content[match.end() :]
            checkbox = Token("html_inline", "", 0)
            state_attr = " checked" if match.group(1).lower() == "x" else ""
            checkbox.content = (
                '<input class="task-list-item-checkbox" type="checkbox" '
                f"disabled{state_attr}> "
            )
            token.children.insert(0, checkbox)
            tokens[idx - 2].attrJoin("class", "task-list-item")

    md.core.ruler.push("task-lists", _rule)


def anchor_plugin(md: MarkdownIt) -> None:
    """为标题生成 id 锚点。"""

    def _rule(state) -> None:
        tokens = state.tokens
        used: dict[str, int] = {}
        for idx, token in enumerate(tokens):
            if token.type != "heading_open":
                continue
            close = idx + 1
            text = _token_text(tokens[close])
            slug = _slugify(text)
            if slug in used:
                used[slug] += 1
                slug = f"{slug}-{used[slug]}"
            else:
                used[slug] = 0
            token.attrSet("id", slug)

    md.core.ruler.push("heading-anchors", _rule)


def build_md() -> MarkdownIt:
    # default 预设含 GFM 表格、删除线等规则；linkify 依赖未安装，显式关闭
    md = MarkdownIt(
        "default",
        {"html": False, "linkify": False, "typographer": False, "breaks": False},
    )
    md.use(callout_plugin)
    md.use(tasklist_plugin)
    md.use(anchor_plugin)
    return md


# --------------------------------------------------------------------------- #
# 四、页面样式与装配
# --------------------------------------------------------------------------- #
# 页面样式已拆分到 styles/md2html.css，见 load_page_css()
PAGE_CSS_FILE = Path(__file__).resolve().parent.parent / "styles" / "md2html.css"


def load_page_css(path: Path | None = None) -> str:
    """读取页面样式表内容。path 为空时使用默认的 styles/md2html.css。"""
    target = path or PAGE_CSS_FILE
    if not target.is_file():
        raise FileNotFoundError(f"找不到样式表: {target}")
    return target.read_text(encoding="utf-8-sig").strip()


MATHJAX_CONFIG = """
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    processEscapes: true
  },
  chtml: { scale: 1.0 },
  options: { enableMenu: false, skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }
};
"""


def build_document(
    body: str, title: str, page_css: str, pygments_css: str, extra_css: str, math: bool
) -> str:
    head = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html_lib.escape(title)}</title>",
        "<style>",
        page_css.strip(),
        pygments_css.strip(),
        extra_css.strip(),
        "</style>",
    ]
    if math:
        head += [
            "<script>",
            MATHJAX_CONFIG.strip(),
            "</script>",
            f'<script id="MathJax-script" async src="{MATHJAX_CDN}"></script>',
        ]
    head += ["</head>", "<body>", '<article class="markdown-body">']
    tail = ["</article>", "</body>", "</html>", ""]
    return "\n".join(head) + "\n" + body.strip("\n") + "\n" + "\n".join(tail)


# --------------------------------------------------------------------------- #
# 五、主流程
# --------------------------------------------------------------------------- #
def convert(
    text: str,
    md: MarkdownIt | None = None,
    mapping: Mapping[str, str] | None = None,
) -> str:
    """把 Markdown 源码转换为 HTML 片段（不含 <html> 外壳）。"""
    md = md or build_md()
    masked, slots = protect(text)
    rendered = md.render(masked)
    return restore(rendered, slots, mapping)


def first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="将 Markdown 转换为自带样式的单文件 HTML（markdown-it-py + MathJax）。"
    )
    parser.add_argument("input", type=Path, help="输入的 .md 文件")
    parser.add_argument(
        "-o", "--output", type=Path, help="输出的 .html 文件（默认与输入同名）"
    )
    parser.add_argument("-t", "--title", help="页面标题（默认取首个一级标题）")
    parser.add_argument(
        "-s",
        "--stylesheet",
        type=Path,
        help=f"主样式表（默认 {PAGE_CSS_FILE}）",
    )
    parser.add_argument("--css", type=Path, help="追加的额外 CSS 文件路径")
    parser.add_argument(
        "-u",
        "--unicode-map",
        type=Path,
        help=f"公式符号映射表（默认 {UNICODE_MATH_FILE}）",
    )
    parser.add_argument(
        "--pygments-style", default="friendly", help="Pygments 配色方案"
    )
    parser.add_argument(
        "--fragment", action="store_true", help="只输出片段，不生成完整页面"
    )
    parser.add_argument("--no-math", action="store_true", help="不加载 MathJax")
    args = parser.parse_args(argv)

    source = args.input
    if not source.is_file():
        print(f"[错误] 找不到文件: {source}", file=sys.stderr)
        return 1

    text = source.read_text(encoding="utf-8-sig")
    title = args.title or first_heading(text) or source.stem

    try:
        page_css = load_page_css(args.stylesheet)
        unicode_math = load_unicode_math(args.unicode_map)
    except FileNotFoundError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    extra_css = args.css.read_text(encoding="utf-8-sig") if args.css else ""
    pygments_css = HtmlFormatter(style=args.pygments_style).get_style_defs(".highlight")

    body = convert(text, mapping=unicode_math)
    output_html = (
        body
        if args.fragment
        else build_document(
            body, title, page_css, pygments_css, extra_css, not args.no_math
        )
    )

    target = args.output or source.with_suffix(".html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output_html, encoding="utf-8", newline="\n")
    print(
        f"[完成] {source} -> {target}  ({len(output_html.encode('utf-8')) / 1024:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
