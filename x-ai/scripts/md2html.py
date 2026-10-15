#!/usr/bin/env python
"""Markdown -> 单文件 HTML 转换器。

基于 markdown-it-py（解析）+ Pygments（代码高亮）+ MathJax（公式渲染），
支持 GFM 表格/删除线、任务列表、GitHub 风格标注（> [!NOTE]）、行内/块级 LaTeX
公式、标题锚点、脚注（``[^1]``）与双链（``[[文件#锚点]]``）；Markdown 中的原始
HTML（``<u>``、``<mark>``、``<center>``、``<div>``、``<video>`` 等）按原样透传，
不做转义。输出自带样式、可直接双击打开的单文件 HTML。

页面样式位于 ../styles/md2html.css，页面脚本位于 md2html.js，公式符号映射位于
unicode-math.json，三者都在生成时读取。生成的 HTML 里**只有 md2html.css 一个样式
来源**：Pygments 的代码高亮配色会被同步进该文件的生成区块（见 sync_pygments_css()），
``--css`` 追加的样式也以 ``<link>`` 引用，因此不会出现额外的 ``<style>`` 内容。

用法::

    micromamba run -n kaggle python scripts/md2html.py md-01-task.md
    micromamba run -n kaggle python scripts/md2html.py input.md -o out.html

默认把样式与脚本内联，得到可外发的单文件 HTML；加 ``-l/--link-css`` /
``--link-js`` 则改为 ``<link>`` / ``<script src>`` 引用，复用共享的
``styles/md2html.css`` 与 ``scripts/md2html.js``（改一处即刻生效，无需重新生成）::

    micromamba run -n kaggle python scripts/md2html.py md-01-task.md -l --link-js
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import os
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
# 三、markdown-it 扩展：任务列表 / 标注 / 标题锚点 / 脚注 / 双链
# --------------------------------------------------------------------------- #
_CALLOUT_RE = re.compile(r"^\[!([A-Za-z]+)\][ \t]*([^\n]*)")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+")
# 表格对齐：markdown-it 默认写 style="text-align:center"，这里换成 class
_TABLE_ALIGN_RE = re.compile(r"^\s*text-align\s*:\s*(left|center|right)\s*;?\s*$")
# 脚注：引用 [^标签] 与定义 [^标签]: 内容
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\s\]]+)\]:[ \t]*")
_FOOTNOTE_REF_RE = re.compile(r"\[\^([^\s\]]+)\]")
# 双链：[[文件#锚点]] / [[文件#锚点|显示文字]]
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")


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
    """生成锚点 id，规则与 GitHub / VSCode（Markdown All in One）一致。

    保留中日韩文字与 ``[A-Za-z0-9_-]``，其余字符丢弃、空白转连字符，最后统一
    小写。小写很关键：目录里手写的 ``#markdown-all-in-one`` 只有在 id 同为小写
    时才能命中 ``Markdown All in One`` 这样的标题。
    """
    slug = re.sub(r"[^\w\u4e00-\u9fff-]", "", text.strip().replace(" ", "-"))
    return slug.strip("-").lower() or "section"


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


def _footnote_ref_html(num: int) -> str:
    """脚注引用的上标链接。"""
    return (
        f'<sup class="footnote-ref">'
        f'<a href="#fn-{num}" id="fnref-{num}" role="doc-noteref">{num}</a></sup>'
    )


def footnote_plugin(md: MarkdownIt) -> None:
    """`[^标签]` 引用 + `[^标签]: 内容` 定义 -> 文末脚注区。

    定义独占一个段落（不跨空行），内容按行内 Markdown 渲染；未被引用的定义会被
    丢弃，引用先按出现顺序编号。
    """

    def _strip_defs(state) -> None:
        tokens = state.tokens
        store: dict[str, str] = state.env.setdefault("footnotes", {})
        drop: list[int] = []
        i = 0
        while i + 2 < len(tokens):
            if (
                tokens[i].type == "paragraph_open"
                and tokens[i + 1].type == "inline"
                and tokens[i + 2].type == "paragraph_close"
            ):
                match = _FOOTNOTE_DEF_RE.match(tokens[i + 1].content)
                if match:
                    body = tokens[i + 1].content[match.end() :].strip()
                    store.setdefault(match.group(1), body)
                    drop.append(i)
                    i += 3
                    continue
            i += 1
        for j in reversed(drop):
            del tokens[j : j + 3]

    def _link_refs(state) -> None:
        store: dict[str, str] = state.env.get("footnotes") or {}
        if not store:
            return
        order: list[str] = []
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            children = token.children
            idx = 0
            while idx < len(children):
                child = children[idx]
                if child.type != "text":
                    idx += 1
                    continue
                segs: list[tuple[str, str]] = []
                last = 0
                for match in _FOOTNOTE_REF_RE.finditer(child.content):
                    label = match.group(1)
                    if label not in store:
                        continue
                    if label not in order:
                        order.append(label)
                    if match.start() > last:
                        segs.append(("text", child.content[last : match.start()]))
                    segs.append(("html", _footnote_ref_html(order.index(label) + 1)))
                    last = match.end()
                if not segs:
                    idx += 1
                    continue
                if last < len(child.content):
                    segs.append(("text", child.content[last:]))
                replaced: list[Token] = []
                for kind, value in segs:
                    piece = Token("text" if kind == "text" else "html_inline", "", 0)
                    piece.content = value
                    replaced.append(piece)
                children[idx : idx + 1] = replaced
                idx += len(replaced)

        if not order:
            return
        items = [
            (
                f'<li id="fn-{num}"><p>{md.renderInline(store[label])} '
                f'<a href="#fnref-{num}" class="footnote-backref" '
                f'role="doc-backlink">\u21a9</a></p></li>'
            )
            for num, label in enumerate(order, start=1)
        ]
        section = Token("html_block", "", 0)
        section.content = (
            '<section class="footnotes" role="doc-endnotes">\n<hr>\n<ol>\n'
            + "\n".join(items)
            + "\n</ol>\n</section>\n"
        )
        state.tokens.append(section)

    md.core.ruler.before("inline", "footnote-definitions", _strip_defs)
    md.core.ruler.after("inline", "footnote-references", _link_refs)


def wikilink_plugin(md: MarkdownIt) -> None:
    """`[[文件#锚点]]`（可带 `|显示文字`）-> 指向同目录 HTML 的链接。"""

    def _rule(state, silent: bool) -> bool:
        if not state.src.startswith("[[", state.pos):
            return False
        match = _WIKILINK_RE.match(state.src, state.pos)
        if not match:
            return False
        if not silent:
            inner = match.group(1).strip()
            target, _, alias = inner.partition("|")
            file_part, _, anchor = target.partition("#")
            file_part, anchor = file_part.strip(), anchor.strip()
            href = file_part
            if href and not href.lower().endswith((".html", ".htm")):
                href = f"{href}.html"
            if anchor:
                href = f"{href}#{_slugify(anchor)}"
            label = alias.strip() or inner
            token = state.push("html_inline", "", 0)
            token.content = (
                f'<a class="wiki-link" href="{html_lib.escape(href, quote=True)}">'
                f"{html_lib.escape(label, quote=False)}</a>"
            )
        state.pos = match.end()
        return True

    md.inline.ruler.before("link", "wikilink", _rule)


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


def table_align_plugin(md: MarkdownIt) -> None:
    """把表格对齐的 ``style="text-align:…"`` 换成 class。

    markdown-it 的表格规则会给 ``:---:`` 这类对齐生成行内 style，那属于「样式」，
    按本工具约定必须落在样式表里，因此改写为 ``class="text-center"`` 等
    （对应规则见 styles/md2html.css）。
    """

    def _rule(state) -> None:
        for token in state.tokens:
            if token.type not in {"th_open", "td_open"}:
                continue
            match = _TABLE_ALIGN_RE.match(str(token.attrGet("style") or ""))
            if not match:
                continue
            token.attrs.pop("style", None)
            token.attrJoin("class", f"text-{match.group(1)}")

    md.core.ruler.push("table-align", _rule)


def build_md() -> MarkdownIt:
    # default 预设含 GFM 表格、删除线等规则；linkify 依赖未安装，显式关闭。
    # html=True：Markdown 里手写的 <u>/<mark>/<center>/<div>/<video> 等原样透传，
    # 教学文档中的「HTML」「CSS」章节依赖这一条。
    md = MarkdownIt(
        "default",
        {"html": True, "linkify": False, "typographer": False, "breaks": False},
    )
    md.use(callout_plugin)
    md.use(tasklist_plugin)
    md.use(footnote_plugin)
    md.use(wikilink_plugin)
    md.use(anchor_plugin)
    md.use(table_align_plugin)
    return md


# --------------------------------------------------------------------------- #
# 四、页面样式与装配
# --------------------------------------------------------------------------- #
# 页面样式已拆分到 styles/md2html.css：默认内联，--link-css 时改为 <link> 复用
PAGE_CSS_FILE = Path(__file__).resolve().parent.parent / "styles" / "md2html.css"
# 页面脚本（代码块「复制」按钮）已拆分到 scripts/md2html.js，同上
PAGE_SCRIPT_FILE = Path(__file__).resolve().parent / "md2html.js"


def load_page_css(path: Path | None = None) -> str:
    """读取页面样式表内容。path 为空时使用默认的 styles/md2html.css。"""
    target = path or PAGE_CSS_FILE
    if not target.is_file():
        raise FileNotFoundError(f"找不到样式表: {target}")
    return target.read_text(encoding="utf-8-sig").strip()


def load_page_script(path: Path | None = None) -> str:
    """读取页面脚本内容。path 为空时使用默认的 scripts/md2html.js。"""
    target = path or PAGE_SCRIPT_FILE
    if not target.is_file():
        raise FileNotFoundError(f"找不到页面脚本: {target}")
    return target.read_text(encoding="utf-8-sig").strip()


# Pygments 配色区块：HTML 里只留一个 <link>，所以高亮规则必须落在样式表中。
# 区块由这两个标记界定，内容由 sync_pygments_css() 维护。
_PYGMENTS_BLOCK_RE = re.compile(
    r"/\* >>> pygments:(\S+)[^\n]*>>> \*/\n(.*?)/\* <<< pygments <<< \*/\n?", re.DOTALL
)


def _pygments_markers(style: str) -> tuple[str, str]:
    return (
        f"/* >>> pygments:{style} — 由 scripts/md2html.py 生成，勿手改本区间 >>> */",
        "/* <<< pygments <<< */",
    )


def sync_pygments_css(path: Path, style: str) -> bool:
    """把 Pygments 配色同步进样式表的生成区块，返回是否改写了文件。

    幂等：样式名与内容都没变时不碰文件（不改 mtime）；区块不存在时追加到文件末尾。
    """
    css = path.read_text(encoding="utf-8-sig")
    begin, end = _pygments_markers(style)
    defs = HtmlFormatter(style=style).get_style_defs(".highlight").strip()
    block = f"{begin}\n{defs}\n{end}\n"

    match = _PYGMENTS_BLOCK_RE.search(css)
    if match:
        if match.group(0) == block:
            return False
        updated = css[: match.start()] + block + css[match.end() :]
    else:
        updated = css.rstrip("\n") + "\n\n" + block
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def relative_href(resource: Path, html_target: Path) -> str:
    """输出 HTML -> 资源文件的相对路径（始终用 / 分隔）。

    让生成的 HTML 直接引用共享的 ``styles/md2html.css`` / ``scripts/md2html.js``，
    资源改一处、所有页面立刻生效。跨盘符无法求相对路径时退回绝对路径。
    """
    try:
        rel = os.path.relpath(resource.resolve(), start=html_target.resolve().parent)
    except ValueError:  # 不同盘符（Windows）
        return resource.resolve().as_posix()
    return Path(rel).as_posix()


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
    body: str,
    title: str,
    *,
    page_css: str = "",
    extra_css_href: str | None = None,
    page_script: str = "",
    math: bool = True,
    css_href: str | None = None,
    script_href: str | None = None,
) -> str:
    """装配完整页面。

    样式只有两种形态，都来自 ``styles/md2html.css``：给出 ``css_href`` 时输出
    ``<link>`` 外链复用，否则把该文件的内容内联进一个 ``<style>``。除此之外不会
    产生任何样式——Pygments 配色（见 ``sync_pygments_css()``）与 ``--css`` 追加
    样式同样走样式表/外链。脚本同理（``--link-js`` 或内联 ``scripts/md2html.js``）。
    """
    head = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{html_lib.escape(title)}</title>",
    ]
    head += [
        f'<link rel="stylesheet" href="{html_lib.escape(href, quote=True)}">'
        for href in (css_href, extra_css_href)
        if href
    ]
    if page_css.strip():
        head += ["<style>", page_css.strip(), "</style>"]
    if math:
        head += [
            "<script>",
            MATHJAX_CONFIG.strip(),
            "</script>",
            f'<script id="MathJax-script" async src="{MATHJAX_CDN}"></script>',
        ]
    head += ["</head>", "<body>", '<article class="markdown-body">']
    tail = ["</article>"]
    if script_href:
        tail.append(
            f'<script src="{html_lib.escape(script_href, quote=True)}"></script>'
        )
    elif page_script.strip():
        tail += ["<script>", page_script.strip(), "</script>"]
    tail += ["</body>", "</html>", ""]
    return "\n".join(head) + "\n" + body.strip("\n") + "\n" + "\n".join(tail)


# --------------------------------------------------------------------------- #
# 五、主流程
# --------------------------------------------------------------------------- #
def convert(
    text: str, md: MarkdownIt | None = None, mapping: Mapping[str, str] | None = None
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
        "-s", "--stylesheet", type=Path, help=f"主样式表（默认 {PAGE_CSS_FILE}）"
    )
    parser.add_argument(
        "-l",
        "--link-css",
        nargs="?",
        const=PAGE_CSS_FILE,
        type=Path,
        metavar="PATH",
        help="不内联主样式表，改为 <link> 引用以便复用（默认复用 styles/md2html.css，"
        "href 按输出 HTML 所在目录算相对路径）",
    )
    parser.add_argument(
        "--link-js",
        nargs="?",
        const=PAGE_SCRIPT_FILE,
        type=Path,
        metavar="PATH",
        help="不内联页面脚本，改为 <script src> 引用以便复用（默认复用 "
        "scripts/md2html.js，同上）",
    )
    parser.add_argument(
        "--css", type=Path, help="追加的额外 CSS 文件（以 <link> 引用）"
    )
    parser.add_argument(
        "-u",
        "--unicode-map",
        type=Path,
        help=f"公式符号映射表（默认 {UNICODE_MATH_FILE}）",
    )
    parser.add_argument(
        "--script", type=Path, help=f"页面脚本（默认 {PAGE_SCRIPT_FILE}）"
    )
    parser.add_argument(
        "--pygments-style",
        default="tango",
        help="代码高亮配色方案，会同步进主样式表的生成区块（默认 tango）",
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
    target = args.output or source.with_suffix(".html")

    # --link-css / --link-js 不带值时，沿用 -s/--stylesheet、--script 或默认路径
    linked_css = args.link_css
    if linked_css == PAGE_CSS_FILE and args.stylesheet is not None:
        linked_css = args.stylesheet
    linked_js = args.link_js
    if linked_js == PAGE_SCRIPT_FILE and args.script is not None:
        linked_js = args.script

    css_target = linked_css or args.stylesheet or PAGE_CSS_FILE
    try:
        if not css_target.is_file():
            raise FileNotFoundError(f"找不到样式表: {css_target}")
        if linked_js is not None and not linked_js.is_file():
            raise FileNotFoundError(f"找不到页面脚本: {linked_js}")
        if args.css is not None and not args.css.is_file():
            raise FileNotFoundError(f"找不到额外样式表: {args.css}")
        unicode_math = load_unicode_math(args.unicode_map)
    except FileNotFoundError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    # 高亮配色写进样式表（HTML 里只留 <link>）；配色方案没变时不碰文件
    if not args.fragment and sync_pygments_css(css_target, args.pygments_style):
        print(f"[样式] 已同步 Pygments 配色到 {css_target}")

    page_css = "" if linked_css is not None else load_page_css(css_target)
    css_href = None if linked_css is None else relative_href(linked_css, target)
    page_script, script_href = load_page_script(args.script), None
    if linked_js is not None:
        page_script, script_href = "", relative_href(linked_js, target)
    extra_css_href = relative_href(args.css, target) if args.css is not None else None

    body = convert(text, mapping=unicode_math)
    output_html = (
        body
        if args.fragment
        else build_document(
            body,
            title,
            page_css=page_css,
            extra_css_href=extra_css_href,
            page_script=page_script,
            math=not args.no_math,
            css_href=css_href,
            script_href=script_href,
        )
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output_html, encoding="utf-8", newline="\n")
    print(
        f"[完成] {source} -> {target}  ({len(output_html.encode('utf-8')) / 1024:.1f} KB)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
