from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from collections.abc import Mapping
from functools import cache
from pathlib import Path

MATHJAX_CDN = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js"

SCRIPT_DIR = Path(__file__).resolve().parent
# 公式中的 Unicode 符号 -> TeX 命令（提高渲染兼容性），见 load_unicode_math()
UNICODE_MATH_FILE = SCRIPT_DIR / "unicode-math.json"
# GitHub Alert 的 octicon 图标（取自 @primer/octicons），见 load_octicons()
OCTICONS_FILE = SCRIPT_DIR / "octicons.json"
# 页面样式 / 页面脚本：生成的 HTML 只引用这两个文件
PAGE_CSS_FILE = SCRIPT_DIR.parent / "styles" / "md2html.css"
PAGE_SCRIPT_FILE = SCRIPT_DIR / "md2html.js"

# 标注（Callout / GitHub Alert）的默认标题
CALLOUT_TITLES = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
}


# --------------------------------------------------------------------------- #
# 一、调用 pandoc
# --------------------------------------------------------------------------- #
@cache
def pandoc_program(explicit: str | None = None) -> str:
    """定位 pandoc 可执行文件（默认取 PATH 上的 pandoc）。"""
    name = explicit or "pandoc"
    found = shutil.which(name)
    if found is None:
        raise FileNotFoundError(f"找不到 pandoc：{name}")
    return found


@cache
def _pandoc_help(program: str) -> str:
    proc = subprocess.run(
        [program, "--help"], capture_output=True, text=True, check=False
    )
    return proc.stdout


def math_flags(program: str) -> list[str]:
    """公式渲染选项：新版 pandoc 用 ``--math-method``，旧版只有 ``--mathjax``。"""
    if "--math-method" in _pandoc_help(program):
        return ["--math-method=mathjax"]
    return ["--mathjax"]


def highlight_flag(program: str, style: str) -> str:
    """代码高亮配色选项，同样兼顾新旧 pandoc 的选项名。"""
    name = "--syntax-highlighting"
    if name not in _pandoc_help(program):
        name = "--highlight-style"
    return f"{name}={style}"


def _run_pandoc(cmd: list[str], source: str) -> str:
    proc = subprocess.run(
        cmd, input=source, capture_output=True, text=True, encoding="utf-8", check=False
    )
    if proc.returncode != 0:
        message = proc.stderr.strip() or f"pandoc 退出码 {proc.returncode}"
        raise RuntimeError(message)
    return proc.stdout


def run_pandoc(
    source: str, *, program: str, from_format: str, to_format: str, highlight_style: str
) -> str:
    """把 Markdown 交给 pandoc，返回 HTML 片段。"""
    cmd = [
        program,
        f"--from={from_format}",
        f"--to={to_format}",
        # preserve：段落内的软换行保留为换行，GitHub Alert 才能区分标记行与正文
        "--wrap=preserve",
        highlight_flag(program, highlight_style),
        *math_flags(program),
    ]
    return _run_pandoc(cmd, source)


_PANDOC_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.DOTALL)


def pandoc_default_css(
    program: str, from_format: str, to_format: str, style: str
) -> str:
    """取 pandoc 默认模板在独立模式下的 ``<style>`` 内容（含代码高亮规则）。

    样本里必须带一个代码块：pandoc 只在文档真的用到高亮时才输出高亮 CSS。
    """
    cmd = [
        program,
        "--standalone",
        f"--from={from_format}",
        f"--to={to_format}",
        highlight_flag(program, style),
    ]
    out = _run_pandoc(cmd, "```python\nx = 1\n```\n")
    match = _PANDOC_STYLE_RE.search(out)
    if match is None:
        raise RuntimeError("未能从 pandoc 输出中提取默认样式")
    return textwrap.dedent(match.group(1)).strip()


# --------------------------------------------------------------------------- #
# 二、HTML 后处理
# --------------------------------------------------------------------------- #
# GitHub Alert：> [!TYPE] 标题（标记行之后的正文属于同一个 <p>）
_ALERT_HEAD_RE = re.compile(r"\s*<p>\s*\[!([A-Za-z]+)\][ \t]*", re.IGNORECASE)
_BLOCKQUOTE_OPEN_RE = re.compile(r"<blockquote(?:\s[^>]*)?>", re.IGNORECASE)
_BLOCKQUOTE_TAG_RE = re.compile(r"<(/?)blockquote(?:\s[^>]*)?>", re.IGNORECASE)
# 表格单元格对齐：pandoc 写 style="text-align: center;"，换成 class
_CELL_ALIGN_RE = re.compile(
    r'(<(?:th|td)\b[^>]*?)\s+style="\s*text-align\s*:\s*(left|center|right)\s*;?\s*"',
    re.IGNORECASE,
)
# 双链：[[文件#锚点]] / [[文件#锚点|显示文字]]
_WIKILINK_RE = re.compile(r"\[\[([^\[\]\n]+?)\]\]")
# 单独成段的元数据标签（pandoc 会把 <link> 包进 <p>）
_META_PARA_RE = re.compile(r"<p>\s*(<(?:link|meta)\b[^>]*>)\s*</p>\n?", re.IGNORECASE)
# 有语言的代码块：pandoc 只把语言写进 class，这里提到 data-lang 供 CSS 显示
_SOURCE_CODE_RE = re.compile(
    r'<div class="sourceCode"([^>]*)>\s*<pre class="sourceCode ([^"]+)">', re.IGNORECASE
)
# 公式：\( … \) 与 \[ … \]
_MATH_SPAN_RE = re.compile(r"(\\\(|\\\[)(.*?)(\\\)|\\\])", re.DOTALL)
# 代码块：其中的内容不参与双链改写
_CODE_SPLIT_RE = re.compile(
    r"(<pre\b[^>]*>|</pre>|<code\b[^>]*>|</code>)", re.IGNORECASE
)


def _matching_blockquote_close(html: str, start: int) -> int:
    """返回与 start 处已打开的 <blockquote> 配对的 </blockquote> 起始位置。"""
    depth = 1
    for match in _BLOCKQUOTE_TAG_RE.finditer(html, start):
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return match.start()
    return -1


@cache
def load_octicons(path: Path | None = None) -> Mapping[str, Mapping[str, str]]:
    """读取 GitHub Alert 用的 octicon 图标表（类型 -> {icon, path}）。"""
    target = path or OCTICONS_FILE
    if not target.is_file():
        raise FileNotFoundError(f"找不到图标表: {target}")
    with target.open(encoding="utf-8") as fp:
        data = json.load(fp)
    return dict(data["icons"])


def alert_icon(kind: str) -> str:
    """生成标注标题前的 octicon，形如 GitHub 自己输出的 ``<svg class="octicon …">``。"""
    table = load_octicons()
    entry = table.get(kind) or table["note"]
    name = entry["icon"]
    return (
        f'<svg class="octicon octicon-{name}" viewBox="0 0 16 16" '
        f'width="16" height="16" aria-hidden="true">'
        f'<path d="{entry["path"]}"></path></svg>'
    )


def _split_alert_head(html: str, head_end: int) -> tuple[str, str, int] | None:
    """拆出标注标题与正文。

    pandoc 把 ``[!TYPE] 标题`` 与紧随其后的正文放进同一个 ``<p>``（软换行），所以
    按行切分；返回 (标题 HTML, 该段残留的正文, 正文起始位置)。
    """
    line_end = html.find("\n", head_end)
    if line_end < 0:
        line_end = len(html)
    line = html[head_end:line_end]

    close_p = line.find("</p>")
    if close_p >= 0:  # 标记独占一段，后面的兄弟节点就是正文
        after = head_end + close_p + len("</p>")
        if html[after : after + 1] == "\n":
            after += 1
        return line[:close_p].strip(), "", after

    para_end = html.find("</p>", line_end)
    if para_end < 0:
        return None
    after = para_end + len("</p>")
    if html[after : after + 1] == "\n":
        after += 1
    return line.strip(), html[line_end + 1 : para_end].strip(), after


def _rewrite_first_alert(html: str) -> str | None:
    for open_match in _BLOCKQUOTE_OPEN_RE.finditer(html):
        head = _ALERT_HEAD_RE.match(html, open_match.end())
        if not head:
            continue
        parts = _split_alert_head(html, head.end())
        close = _matching_blockquote_close(html, open_match.end())
        if parts is None or close < 0:
            continue

        kind = head.group(1).lower()
        title, head_body, body_start = parts
        title = title or CALLOUT_TITLES.get(kind, kind.title())
        body = html[body_start:close].strip("\n")
        if head_body:
            body = f"<p>{head_body}</p>\n{body}".rstrip()
        body_html = f"{body}\n" if body else ""
        # 与 GitHub 自己生成的 HTML 保持一致：div.markdown-alert + 标题里的 octicon
        replacement = (
            f'<div class="markdown-alert markdown-alert-{kind}">'
            f'<p class="markdown-alert-title">{alert_icon(kind)}{title}</p>\n'
            f"{body_html}</div>"
        )
        tail = close + len("</blockquote>")
        return f"{html[: open_match.start()]}{replacement}{html[tail:]}"
    return None


def transform_alerts(html: str) -> str:
    """把 ``> [!TYPE]`` 引用块改写成 GitHub Alert 结构。

    每轮至少吃掉一个 ``[!TYPE]`` 标记，因此必然收敛；嵌套引用也能逐层处理。
    """
    while True:
        rewritten = _rewrite_first_alert(html)
        if rewritten is None:
            return html
        html = rewritten


def _replace_cell_align(match: re.Match[str]) -> str:
    tag, align = match.group(1), match.group(2).lower()
    existing = re.search(r'class="([^"]*)"', tag)
    if existing:
        merged = f"{existing.group(1)} text-{align}"
        tag = f'{tag[: existing.start()]}class="{merged}"{tag[existing.end() :]}'
    else:
        tag = f'{tag} class="text-{align}"'
    return tag


def transform_table_align(html: str) -> str:
    """表格对齐由行内 style 改为 class，样式统一落在样式表里。"""
    return _CELL_ALIGN_RE.sub(_replace_cell_align, html)


def unwrap_metadata_paragraphs(html: str) -> str:
    """pandoc 会把单独成行的 ``<link>`` / ``<meta>`` 包进 ``<p>``，这里还原。"""
    return _META_PARA_RE.sub(lambda m: f"{m.group(1)}\n", html)


def annotate_code_languages(html: str) -> str:
    """把代码块的语言从 ``class`` 提到 ``data-lang``，供样式表显示角标。"""

    def _sub(match: re.Match[str]) -> str:
        attrs, lang = match.group(1), match.group(2).strip()
        label = html_lib.escape(lang, quote=True)
        return (
            f'<div class="sourceCode" data-lang="{label}"{attrs}>'
            f'<pre class="sourceCode {lang}">'
        )

    return _SOURCE_CODE_RE.sub(_sub, html)


def anchor_slug(text: str) -> str:
    """把标题文本规范化成锚点，规则与 pandoc 的 auto_identifiers 一致。"""
    slug = re.sub(r"[^\w\u4e00-\u9fff.-]", "", text.strip().replace(" ", "-"))
    return slug.strip("-").lower()


def _replace_wikilink(match: re.Match[str]) -> str:
    inner = match.group(1).strip()
    target, _, alias = inner.partition("|")
    file_part, _, anchor = target.partition("#")
    file_part, anchor = file_part.strip(), anchor.strip()
    href = file_part
    if href and not href.lower().endswith((".html", ".htm")):
        href = f"{href}.html"
    if anchor:
        href = f"{href}#{anchor_slug(anchor)}"
    label = alias.strip() or inner
    return (
        f'<a class="wiki-link" href="{html_lib.escape(href, quote=True)}">'
        f"{html_lib.escape(label, quote=False)}</a>"
    )


def transform_wikilinks(html: str) -> str:
    """``[[文件#锚点]]`` -> 指向同目录 HTML 的链接；代码块内保持原样。"""
    out: list[str] = []
    depth = 0
    for part in _CODE_SPLIT_RE.split(html):
        lowered = part.lower()
        if lowered.startswith(("<pre", "<code")):
            depth += 1
            out.append(part)
        elif lowered.startswith(("</pre", "</code")):
            depth = max(depth - 1, 0)
            out.append(part)
        elif depth:
            out.append(part)
        else:
            out.append(_WIKILINK_RE.sub(_replace_wikilink, part))
    return "".join(out)


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


def normalize_math(html: str, mapping: Mapping[str, str] | None = None) -> str:
    """把公式区间内的 Unicode 符号换成 TeX 命令，提高 MathJax 兼容性。"""
    if "\\(" not in html and "\\[" not in html:
        return html

    def _sub(match: re.Match[str]) -> str:
        inner = _normalize_tex(match.group(2), mapping)
        return f"{match.group(1)}{inner}{match.group(3)}"

    return _MATH_SPAN_RE.sub(_sub, html)


def postprocess(html: str, mapping: Mapping[str, str] | None = None) -> str:
    """pandoc 输出 -> 本工具约定的 HTML 片段。"""
    html = unwrap_metadata_paragraphs(html)
    html = annotate_code_languages(html)
    html = transform_alerts(html)
    html = transform_table_align(html)
    html = transform_wikilinks(html)
    return normalize_math(html, mapping)


def convert(
    text: str,
    *,
    program: str,
    from_format: str = "markdown",
    to_format: str = "html5",
    highlight_style: str = "tango",
    mapping: Mapping[str, str] | None = None,
) -> str:
    """Markdown 源码 -> HTML 片段（pandoc + 后处理，不含 <html> 外壳）。"""
    raw = run_pandoc(
        text,
        program=program,
        from_format=from_format,
        to_format=to_format,
        highlight_style=highlight_style,
    )
    return postprocess(raw, mapping)


def first_heading(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


# --------------------------------------------------------------------------- #
# 三、样式表 / 页面脚本装配
# --------------------------------------------------------------------------- #
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


# 样式表中由本脚本维护的 pandoc 默认样式区块，避免 HTML 里再出现 <style>
_PANDOC_BLOCK_RE = re.compile(
    r"/\* >>> pandoc:(\S+)[^\n]*>>> \*/\n(.*?)/\* <<< pandoc <<< \*/\n?", re.DOTALL
)


def _pandoc_markers(style: str) -> tuple[str, str]:
    return (
        f"/* >>> pandoc:{style} — 由 scripts/md2html.py 生成，勿手改本区间 >>> */",
        "/* <<< pandoc <<< */",
    )


def sync_pandoc_css(
    path: Path, program: str, from_format: str, to_format: str, style: str
) -> bool:
    """把 pandoc 默认样式同步进样式表的生成区块，返回是否改写了文件。

    幂等：配色方案与内容都没变时不碰文件（不改 mtime）；区块不存在时追加到末尾。
    """
    css = path.read_text(encoding="utf-8-sig")
    begin, end = _pandoc_markers(style)
    defs = pandoc_default_css(program, from_format, to_format, style)
    block = f"{begin}\n{defs}\n{end}\n"

    match = _PANDOC_BLOCK_RE.search(css)
    if match:
        if match.group(0) == block:
            return False
        updated = f"{css[: match.start()]}{block}{css[match.end() :]}"
    else:
        updated = f"{css.rstrip()}\n\n{block}"
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


MATHJAX_CONFIG = """
window.MathJax = {
  tex: {
    inlineMath: [['\\\\(', '\\\\)']],
    displayMath: [['\\\\[', '\\\\]']],
    processEscapes: true
  },
  chtml: { scale: 1.0 },
  options: {
    enableMenu: false,
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
  }
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
    产生任何样式——代码高亮配色见 ``sync_highlight_css()``，``--css`` 追加样式也走
    ``<link>``。脚本同理（``--link-js`` 或内联 ``scripts/md2html.js``）。
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
# 四、主流程
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="用 pandoc 把 Markdown 转成 HTML 并补上 GitHub Alert；"
        "生成的页面只有一个样式来源 styles/md2html.css。"
    )
    parser.add_argument("input", type=Path, help="输入的 .md 文件")
    parser.add_argument(
        "-o", "--output", type=Path, help="输出的 .html 文件（默认与输入同名）"
    )
    parser.add_argument("-t", "--title", help="页面标题（默认取首个一级标题）")
    parser.add_argument("--pandoc", help="pandoc 可执行文件（默认取 PATH 上的 pandoc）")
    parser.add_argument(
        "--from", dest="from_format", default="markdown", help="pandoc 输入格式"
    )
    parser.add_argument(
        "--to", dest="to_format", default="html5", help="pandoc 输出格式"
    )
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
        "--css", type=Path, help="追加的额外 CSS 文件（以 <link> 引用）"
    )
    parser.add_argument(
        "--script", type=Path, help=f"页面脚本（默认 {PAGE_SCRIPT_FILE}）"
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
        "-u",
        "--unicode-map",
        type=Path,
        help=f"公式符号映射表（默认 {UNICODE_MATH_FILE}）",
    )
    parser.add_argument(
        "--highlight-style",
        default="tango",
        help="代码高亮配色方案，决定同步进样式表的 pandoc 默认样式（默认 tango）",
    )
    parser.add_argument(
        "--fragment", action="store_true", help="只输出片段，不生成完整页面"
    )
    parser.add_argument(
        "--no-math", action="store_true", help="不加载 MathJax（公式仍按 \\(…\\) 输出）"
    )
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
        program = pandoc_program(args.pandoc)
        if not css_target.is_file():
            raise FileNotFoundError(f"找不到样式表: {css_target}")
        if linked_js is not None and not linked_js.is_file():
            raise FileNotFoundError(f"找不到页面脚本: {linked_js}")
        if args.css is not None and not args.css.is_file():
            raise FileNotFoundError(f"找不到额外样式表: {args.css}")
        unicode_math = load_unicode_math(args.unicode_map)
        load_octicons()  # 标注图标：缺了就在这里报错，别等转换到一半
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1

    # pandoc 默认样式写进样式表（HTML 里只留 <link>）；没变化时不碰文件
    if not args.fragment:
        try:
            changed = sync_pandoc_css(
                css_target,
                program,
                args.from_format,
                args.to_format,
                args.highlight_style,
            )
            if changed:
                print(f"[样式] 已同步 pandoc 默认样式到 {css_target}")
        except RuntimeError as exc:
            print(f"[警告] 无法同步 pandoc 默认样式：{exc}", file=sys.stderr)

    page_css = "" if linked_css is not None else load_page_css(css_target)
    css_href = None if linked_css is None else relative_href(linked_css, target)
    page_script, script_href = load_page_script(args.script), None
    if linked_js is not None:
        page_script, script_href = "", relative_href(linked_js, target)
    extra_css_href = relative_href(args.css, target) if args.css is not None else None

    try:
        body = convert(
            text,
            program=program,
            from_format=args.from_format,
            to_format=args.to_format,
            highlight_style=args.highlight_style,
            mapping=unicode_math,
        )
    except RuntimeError as exc:
        print(f"[错误] pandoc 转换失败：{exc}", file=sys.stderr)
        return 1

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
    size = len(output_html.encode("utf-8")) / 1024
    print(f"[完成] {source} -> {target}  ({size:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
