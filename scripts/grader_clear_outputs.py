#!/usr/bin/env python3
"""批量清理 .ipynb 的运行输出，基于官方 jupyter nbconvert 的 ClearOutputPreprocessor。

清理范围：每个 code cell 的 outputs 与 execution_count，以及 nbconvert
一并移除的运行时 cell.metadata（execution / collapsed / scrolled 等）。
源码、Markdown、附件与 notebook 结构保持不变。

用法：
    python clear_notebook_outputs.py                          # 清理默认目录
    python clear_notebook_outputs.py --dir D:/path/to/nbs     # 指定目录
    python clear_notebook_outputs.py --recursive              # 递归子目录
    python clear_notebook_outputs.py --dry-run                # 只统计，不改动
    python clear_notebook_outputs.py --no-backup              # 不生成清理前备份
    python clear_notebook_outputs.py --jupyter "jupyter nbconvert"  # 手写 jupyter 命令

依赖：Python 标准库 + 可用的 jupyter nbconvert。
    若系统 PATH 中没有 jupyter，脚本会自动回退到 `uvx --from nbconvert jupyter-nbconvert`。
"""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# 默认目标：与本脚本同级的 智能B241-03 目录
DEFAULT_DIR = Path(__file__).resolve().parent / "智能B241-03"


def collect(root: Path, recursive: bool) -> list[Path]:
    it = root.rglob("*.ipynb") if recursive else root.glob("*.ipynb")
    # 跳过 Jupyter 自动生成的检查点文件
    return sorted(p for p in it if ".ipynb_checkpoints" not in p.parts)


def scan(files: list[Path]) -> dict:
    """用标准库统计输出规模，不依赖 nbformat，可用于清理前后的对照。"""
    st = dict(
        files=0, bytes=0, cells=0, code_cells=0,
        cells_with_outputs=0, outputs=0, cells_with_exec_count=0,
    )
    for f in files:
        nb = json.loads(f.read_text(encoding="utf-8"))
        st["files"] += 1
        st["bytes"] += f.stat().st_size
        for c in nb.get("cells", []):
            st["cells"] += 1
            if c.get("cell_type") != "code":
                continue
            st["code_cells"] += 1
            outs = c.get("outputs") or []
            if outs:
                st["cells_with_outputs"] += 1
                st["outputs"] += len(outs)
            if c.get("execution_count") is not None:
                st["cells_with_exec_count"] += 1
    return st


def resolve_jupyter(explicit: str | None) -> list[str]:
    """返回一个基础命令：后面可直接拼接 nbconvert 的参数与文件列表。"""
    if explicit:
        return shlex.split(explicit)
    exe = shutil.which("jupyter")
    if exe:
        return [exe, "nbconvert"]
    exe = shutil.which("jupyter-nbconvert")
    if exe:
        return [exe]
    probe = subprocess.run(
        [sys.executable, "-c", "import jupyter_core, nbconvert"],
        capture_output=True,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "jupyter", "nbconvert"]
    if shutil.which("uvx"):
        return ["uvx", "--from", "nbconvert", "jupyter-nbconvert"]
    raise RuntimeError(
        "未找到 jupyter nbconvert。请执行 `pip install nbconvert` "
        "或 `uv tool install nbconvert` 后重试。"
    )


def backup(root: Path, files: list[Path]) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = root.parent / f"{root.name}_清理前备份_{ts}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.relative_to(root.parent))
    return out


def clear_batch(base_cmd: list[str], batch: list[Path]) -> tuple[bool, str]:
    cmd = base_cmd + [
        "--to", "notebook",
        "--ClearOutputPreprocessor.enabled=True",
        "--inplace",
        *[str(f) for f in batch],
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout or "").strip()


def show(tag: str, st: dict) -> None:
    print(
        f"{tag}: {st['files']} 个文件 / {st['bytes'] / 1024:.1f} KiB | "
        f"{st['cells']} cells（code {st['code_cells']}）| "
        f"带输出 cell {st['cells_with_outputs']}（共 {st['outputs']} 个 output）| "
        f"带执行序号 cell {st['cells_with_exec_count']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="用 jupyter nbconvert 批量清理 .ipynb 输出")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="目标目录（默认脚本同级 智能B241-03）")
    ap.add_argument("--recursive", action="store_true", help="递归处理子目录")
    ap.add_argument("--dry-run", action="store_true", help="只统计待清理内容，不改动文件")
    ap.add_argument("--no-backup", action="store_true", help="不生成清理前 zip 备份")
    ap.add_argument("--jupyter", help='显式指定 jupyter 命令，如 "jupyter nbconvert"')
    ap.add_argument("--batch-size", type=int, default=20, help="单次调用处理的文件数（默认 20）")
    args = ap.parse_args()

    root = args.dir.resolve()
    if not root.is_dir():
        print(f"目录不存在: {root}", file=sys.stderr)
        return 2
    files = collect(root, args.recursive)
    if not files:
        print(f"未找到 .ipynb 文件: {root}", file=sys.stderr)
        return 2

    print(f"目标目录: {root}")
    show("清理前", scan(files))
    if args.dry_run:
        print("dry-run：未修改任何文件。")
        return 0

    base_cmd = resolve_jupyter(args.jupyter)
    print(f"使用命令: {' '.join(base_cmd)} --to notebook --ClearOutputPreprocessor.enabled=True --inplace")

    if not args.no_backup:
        z = backup(root, files)
        print(f"备份已生成: {z}")

    failed: list[tuple[str, str]] = []
    batches = [files[i:i + args.batch_size] for i in range(0, len(files), args.batch_size)]
    for batch in batches:
        ok, msg = clear_batch(base_cmd, batch)
        if ok:
            print(f"  已处理 {len(batch)} 个文件")
            continue
        # 整批失败时逐个重试，定位到具体文件
        for f in batch:
            ok2, msg2 = clear_batch(base_cmd, [f])
            if not ok2:
                failed.append((f.name, msg2[-300:]))
    for name, msg in failed:
        print(f"  失败: {name} -> {msg}", file=sys.stderr)

    show("清理后", scan(files))
    if failed:
        print(f"完成，但有 {len(failed)} 个文件失败。", file=sys.stderr)
        return 1
    print(f"完成：{len(files)} 个 notebook 的输出已清空。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
