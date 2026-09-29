#!/usr/bin/env python3
"""白噪声 / 粉噪声 / 棕噪声 生成器：命令行 + tkinter 图形界面合一。

基于系统 ffmpeg 的 anoisesrc 滤镜生成噪声，支持通过命令行参数或图形界面调节：
  - 时长（秒）
  - 噪声类型：white / pink / brown
  - 采样率
  - 音量（振幅）
  - 输出格式（mp3 / wav）与文件名

图形界面依赖 tkinter（系统 uv 环境自带 Tk 9.0）。运行：
  # 图形界面（默认）
  uv run --no-project noise_gui.py
  uv run --no-project noise_gui.py --gui

  # 命令行
  uv run --no-project noise_gui.py -d 300                 # 5 分钟白噪声 -> noise.mp3
  uv run --no-project noise_gui.py -d 180 -c pink -o p.mp3
  uv run --no-project noise_gui.py -d 60 -c brown -f wav -r 48000 -v 0.3
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------- 生成逻辑（仅标准库，无需 tkinter） ----------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="生成白噪声 / 粉噪声 / 棕噪声音频（依赖 ffmpeg）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=None,
        help="音频时长，单位秒（支持小数，如 2.5）；不指定则启动图形界面",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="noise.mp3",
        help="输出文件路径；扩展名决定格式（.mp3 / .wav）",
    )
    parser.add_argument(
        "-c",
        "--color",
        choices=["white", "pink", "brown"],
        default="white",
        help="噪声类型",
    )
    parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=44100,
        help="采样率（Hz）",
    )
    parser.add_argument(
        "-v",
        "--volume",
        type=float,
        default=0.5,
        help="噪声振幅（0.0–1.0）。ffmpeg anoisesrc 的 a 参数",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["mp3", "wav"],
        default=None,
        help="输出格式；默认按输出文件扩展名推断",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=2,
        help="声道数（1=单声道，2=立体声）",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动图形界面（默认；不传 -d 时也会启动）",
    )
    return parser


def resolve_format(output: str, fmt: str | None) -> str:
    if fmt:
        return fmt
    if output.lower().endswith(".wav"):
        return "wav"
    return "mp3"


def build_ffmpeg_cmd(
    duration: float,
    output: str,
    color: str = "white",
    sample_rate: int = 44100,
    volume: float = 0.5,
    channels: int = 2,
    fmt: str | None = None,
) -> list[str]:
    """构造 ffmpeg 命令行（不执行）。"""
    fmt = resolve_format(output, fmt)
    # anoisesrc 生成单声道噪声，再用 -ac 设置目标声道数
    filter_chain = f"anoisesrc=d={duration:.6f}:c={color}:r={sample_rate}:a={volume}"
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_chain,
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
    ]
    if fmt == "mp3":
        cmd += ["-c:a", "libmp3lame", "-q:a", "4"]
    else:  # wav
        cmd += ["-c:a", "pcm_s16le"]
    cmd.append(output)
    return cmd


def generate(
    duration: float,
    output: str,
    color: str = "white",
    sample_rate: int = 44100,
    volume: float = 0.5,
    channels: int = 2,
    fmt: str | None = None,
) -> bool:
    """生成噪声音频，成功返回 True。ffmpeg 缺失或执行失败返回 False。"""
    if shutil.which("ffmpeg") is None:
        print("错误：未找到 ffmpeg，请先安装并加入 PATH。", file=sys.stderr)
        return False
    if duration <= 0:
        print("错误：时长必须为正数。", file=sys.stderr)
        return False
    if not (0.0 <= volume <= 1.0):
        print("错误：音量（振幅）必须在 0.0–1.0 之间。", file=sys.stderr)
        return False

    fmt = resolve_format(output, fmt)
    cmd = build_ffmpeg_cmd(duration, output, color, sample_rate, volume, channels, fmt)
    print(
        f"生成噪声：时长={duration}s 类型={color} "
        f"采样率={sample_rate}Hz 声道={channels} 振幅={volume} "
        f"格式={fmt} -> {output}"
    )
    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as exc:
        print("ffmpeg 执行失败：", exc.stderr.decode(errors="replace"), file=sys.stderr)
        return False
    print("完成。")
    return True


# ---------- 图形界面（ttk） ----------


class NoiseGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("白噪声生成器")
        root.resizable(False, False)

        # 深色/浅色自适应由系统主题决定，这里用 ttk 原生控件
        self._build_widgets()
        self._busy = False

    # ---------- 界面布局 ----------
    def _build_widgets(self) -> None:
        # 时长
        f_dur = ttk.LabelFrame(self.root, text="时长")
        f_dur.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.duration = tk.DoubleVar(value=300.0)
        ttk.Entry(f_dur, textvariable=self.duration, width=12).pack(side="left", padx=4)
        ttk.Label(f_dur, text="秒").pack(side="left")
        for label, secs in [("1 分", 60), ("3 分", 180), ("5 分", 300), ("10 分", 600)]:
            ttk.Button(
                f_dur,
                text=label,
                width=6,
                command=lambda s=secs: self.duration.set(float(s)),
            ).pack(side="left", padx=2)

        # 噪声类型
        f_color = ttk.LabelFrame(self.root, text="噪声类型")
        f_color.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        self.color = tk.StringVar(value="white")
        for text, val in [("白噪声", "white"), ("粉噪声", "pink"), ("棕噪声", "brown")]:
            ttk.Radiobutton(f_color, text=text, variable=self.color, value=val).pack(
                side="left", padx=6
            )

        # 采样率
        f_rate = ttk.LabelFrame(self.root, text="采样率")
        f_rate.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.sample_rate = tk.IntVar(value=44100)
        ttk.Combobox(
            f_rate,
            textvariable=self.sample_rate,
            width=10,
            state="readonly",
            values=["22050", "44100", "48000"],
        ).pack(padx=4)

        # 音量
        f_vol = ttk.LabelFrame(self.root, text="音量（振幅）")
        f_vol.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.volume = tk.DoubleVar(value=0.5)
        ttk.Scale(
            f_vol,
            variable=self.volume,
            from_=0.0,
            to=1.0,
            orient="horizontal",
            length=280,
            command=lambda _: self.vol_label.config(text=f"{self.volume.get():.2f}"),
        ).pack(side="left", padx=6)
        self.vol_label = ttk.Label(f_vol, text="0.50", width=6)
        self.vol_label.pack(side="left")

        # 声道 + 格式
        f_opt = ttk.LabelFrame(self.root, text="输出选项")
        f_opt.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.channels = tk.IntVar(value=2)
        ttk.Radiobutton(f_opt, text="立体声", variable=self.channels, value=2).pack(
            side="left", padx=6
        )
        ttk.Radiobutton(f_opt, text="单声道", variable=self.channels, value=1).pack(
            side="left", padx=6
        )
        self.fmt = tk.StringVar(value="mp3")
        ttk.Radiobutton(f_opt, text="MP3", variable=self.fmt, value="mp3").pack(
            side="left", padx=6
        )
        ttk.Radiobutton(f_opt, text="WAV", variable=self.fmt, value="wav").pack(
            side="left", padx=6
        )

        # 输出文件
        f_out = ttk.LabelFrame(self.root, text="输出文件")
        f_out.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.output = tk.StringVar(value="noise.mp3")
        ttk.Entry(f_out, textvariable=self.output, width=30).pack(
            side="left", padx=4, fill="x", expand=True
        )
        ttk.Button(f_out, text="浏览…", command=self._browse).pack(side="left", padx=4)

        # 生成按钮 + 状态
        self.status = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status, anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=4
        )
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        ttk.Button(self.root, text="生成", command=self._on_generate).grid(
            row=7, column=0, columnspan=2, pady=6
        )

    # ---------- 交互逻辑 ----------
    def _browse(self) -> None:
        init = self.output.get() or "noise.mp3"
        path = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            initialfile=os.path.basename(init),
            filetypes=[("MP3", "*.mp3"), ("WAV", "*.wav"), ("All", "*.*")],
        )
        if path:
            self.output.set(path)
            if path.lower().endswith(".wav"):
                self.fmt.set("wav")
            else:
                self.fmt.set("mp3")

    def _on_generate(self) -> None:
        if self._busy:
            return
        # 参数校验
        try:
            dur = float(self.duration.get())
        except (tk.TclError, ValueError):
            messagebox.showerror("错误", "时长必须是数字（秒）。")
            return
        if dur <= 0:
            messagebox.showerror("错误", "时长必须为正数。")
            return
        out = self.output.get().strip()
        if not out:
            messagebox.showerror("错误", "请填写输出文件路径。")
            return
        if not (0.0 <= self.volume.get() <= 1.0):
            messagebox.showerror("错误", "音量必须在 0.0–1.0 之间。")
            return

        self._busy = True
        self.progress.start(15)
        self.status.set(f"正在生成：{out} …")
        threading.Thread(
            target=self._worker,
            args=(dur, out),
            daemon=True,
        ).start()

    def _worker(self, dur: float, out: str) -> None:
        ok = generate(
            duration=dur,
            output=out,
            color=self.color.get(),
            sample_rate=int(self.sample_rate.get()),
            volume=float(self.volume.get()),
            channels=int(self.channels.get()),
            fmt=self.fmt.get(),
        )
        # 回到主线程更新 UI
        self.root.after(0, self._finish, ok, out)

    def _finish(self, ok: bool, out: str) -> None:
        self.progress.stop()
        self._busy = False
        if ok:
            self.status.set(f"完成：{out}")
            messagebox.showinfo("完成", f"已生成：\n{out}")
        else:
            self.status.set("生成失败，详见控制台。")
            messagebox.showerror("失败", "生成失败，请确认 ffmpeg 已安装并在 PATH 中。")


def launch_gui() -> None:
    root = tk.Tk()
    NoiseGeneratorApp(root)
    root.mainloop()


# ---------- 入口 ----------


def main() -> int:
    args = build_parser().parse_args()
    if args.gui or args.duration is None:
        launch_gui()
        return 0
    return (
        0
        if generate(
            args.duration,
            args.output,
            args.color,
            args.sample_rate,
            args.volume,
            args.channels,
            args.format,
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
