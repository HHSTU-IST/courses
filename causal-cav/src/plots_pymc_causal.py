from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cav_common as C
import matplotlib.pyplot as plt

# 图内显示名（报告读者为临床医生，图上不应出现代码式参数名）。
# 数据文件（CSV）里的键名保持英文不变，只换图上与报告中的显示文字。
PARAM_LABELS: dict[str, tuple[str, str]] = {
    "a_male": ("性别（男）效应", "male effect"),
    "a_age": ("年龄效应（每 1 岁）", "age effect (per year)"),
    "lam_d": ("DWI 载荷", "DWI loading"),
    "lam_t": ("T2WI 载荷", "T2WI loading"),
    "sd[0]": ("SWI 测量残差 SD", "SWI residual SD"),
    "sd[1]": ("DWI 测量残差 SD", "DWI residual SD"),
    "sd[2]": ("T2WI 测量残差 SD", "T2WI residual SD"),
    "c0": ("检出方程截距", "detection intercept"),
    "c1": ("检出方程斜率", "detection slope"),
    "tau_loc": ("部位效应尺度 τ", "location scale tau"),
    "eff_age_10y": ("年龄效应（每 +10 岁，倍数）", "age effect per +10 y (ratio)"),
    "eff_male": ("男性效应（倍数）", "male effect (ratio)"),
    "p_detect_Lm1": ("检出概率（小病灶）", "detection prob. (small)"),
    "p_detect_L0": ("检出概率（中等病灶）", "detection prob. (medium)"),
    "p_detect_Lp1": ("检出概率（大病灶）", "detection prob. (large)"),
}


def param_label(name: str) -> str:
    """参数显示名；未登记的参数退回原名。"""
    return C.L(*PARAM_LABELS.get(name, (name, name)))


def _latent_table() -> pd.DataFrame:
    return C.read_table("03_pymc_潜变量后验.csv")


def _samples() -> pd.DataFrame:
    return C.read_table("03_pymc_关键参数后验样本.csv")


def _model_a_params() -> pd.DataFrame:
    return C.read_table("03_pymc_模型A参数.csv").set_index("参数")


# =========================================================================== #
# 图 10：潜变量 L 与三个测量（读 03_pymc_潜变量后验.csv）
# =========================================================================== #
def fig10_latent() -> Path:
    tbl = _latent_table()
    L = tbl["L后验均值"].to_numpy()
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8))
    for ax, col, lab in zip(
        axes, ["log_t2", "log_dwi", "log_swi"], ["log T2WI", "log DWI", "log SWI"]
    ):
        v = tbl[col].to_numpy()
        m = ~np.isnan(v)
        ax.scatter(L[m], v[m], s=26, alpha=0.75, color="#2c3e50")
        b, a = np.polyfit(L[m], v[m], 1)
        xs = np.linspace(L.min(), L.max(), 50)
        ax.plot(xs, a + b * xs, color="#c0392b", lw=1.6)
        ax.set_xlabel(C.L("潜变量 L 后验均值", "posterior mean of L"))
        ax.set_ylabel(lab)
        ax.set_title(f"{lab}  ~ 斜率 {b:.3f}", fontsize=9.5)
    fig.suptitle(
        C.L(
            "图 10  潜变量 L 与三个测量的关系（斜率即相对灵敏度）",
            "Fig 10  Latent L vs three measurements",
        ),
        fontsize=10,
    )
    fig.tight_layout()
    return C.savefig(fig, "fig10_pymc_latent.png")


# =========================================================================== #
# 图 11：直接通路检验与载荷稳定性（读 03_pymc_关键参数后验样本.csv）
# =========================================================================== #
def fig11_delta() -> Path:
    smp = _samples()
    dl = smp["delta"].to_numpy()
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.6))
    ax = axes[0]
    ax.hist(dl, bins=45, color="#8e44ad", alpha=0.8, density=True)
    lo, hi = np.percentile(dl, [2.5, 97.5])
    ax.axvline(0, color="#c0392b", lw=1.6, ls="--")
    ax.axvspan(lo, hi, color="#8e44ad", alpha=0.12)
    ax.set_title(
        C.L(
            f"delta（DWI→SWI 直接效应）95%HDI [{lo:.2f}, {hi:.2f}]",
            f"delta 95%HDI [{lo:.2f}, {hi:.2f}]",
        ),
        fontsize=9.5,
    )
    ax.set_xlabel(C.L("控制真实大小 L 后的直接效应", "direct effect given L"))

    ax = axes[1]
    for col, lab, c in (
        ("lam_d_A", "A 共因模型", "#2980b9"),
        ("lam_d_C", "C +直接通路", "#8e44ad"),
    ):
        ax.hist(
            smp[col].to_numpy(), bins=40, alpha=0.55, label=lab, color=c, density=True
        )
    ax.set_title(
        C.L("DWI 载荷 λ（相对 SWI）", "DWI loading (relative to SWI)"), fontsize=9.5
    )
    ax.legend(frameon=False, fontsize=8.5)
    fig.suptitle(
        C.L("图 11  直接因果通路检验与载荷稳定性", "Fig 11  Direct-path test"),
        fontsize=10,
    )
    fig.tight_layout()
    return C.savefig(fig, "fig11_pymc_delta.png")


# =========================================================================== #
# 图 12：模型 A 参数后验森林图（读 03_pymc_模型A参数.csv）
# =========================================================================== #
def _forest(res: pd.DataFrame, name: str, title: str) -> Path:
    d = res.dropna(subset=["95%HDI 下", "95%HDI 上"]).copy()
    d = d.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.6, max(2.6, 0.34 * len(d) + 1.4)))
    y = np.arange(len(d))
    ax.errorbar(
        d["后验均值"],
        y,
        xerr=[d["后验均值"] - d["95%HDI 下"], d["95%HDI 上"] - d["后验均值"]],
        fmt="o",
        color="#2980b9",
        ecolor="#7f8c8d",
        capsize=3,
        ms=5,
    )
    ax.axvline(0, color="#c0392b", lw=1, ls="--")
    ax.set_yticks(y, [param_label(str(i)) for i in d.index])
    ax.set_xlabel(C.L("后验均值与 95% 最高密度区间", "posterior mean & 95% HDI"))
    ax.set_title(title, fontsize=10)
    fig.tight_layout()
    return C.savefig(fig, name)


def fig12_forest() -> Path:
    return _forest(
        _model_a_params(),
        "fig12_pymc_forest.png",
        C.L("图 12  模型 A 参数后验（森林图）", "Fig 12  Model A posteriors"),
    )


# =========================================================================== #
FIGS: dict[str, Callable[[], Path]] = {
    "fig10": fig10_latent,
    "fig11": fig11_delta,
    "fig12": fig12_forest,
}

# 每张图依赖的绘图输入（用于缺失时给出可操作的提示）
INPUTS: dict[str, list[str]] = {
    "fig10": ["03_pymc_潜变量后验.csv"],
    "fig11": ["03_pymc_关键参数后验样本.csv"],
    "fig12": ["03_pymc_模型A参数.csv"],
}


def _check_inputs(names: Sequence[str]) -> None:
    missing = sorted({f for n in names for f in INPUTS[n] if not (C.DAT / f).is_file()})
    if missing:
        raise SystemExit(
            "缺少绘图输入：\n  " + "\n  ".join(missing) + f"\n（应位于 {C.DAT}）\n"
            "请先运行：micromamba run -n kaggle python src/02_pymc_causal.py"
        )


def main(want: Sequence[str] | None = None) -> None:
    names = list(FIGS) if not want else [n for n in want if n in FIGS]
    unknown = [n for n in (want or []) if n not in FIGS]
    if unknown:
        raise SystemExit(f"未知的图名 {unknown}；可选：{', '.join(FIGS)}")
    if not names:
        return
    _check_inputs(names)
    C.setup_matplotlib()
    print("=" * 78)
    print("绘图：第 3 步（只读 data，不重新采样）")
    print("=" * 78)
    for n in names:
        FIGS[n]()
    print(f"完成，共 {len(names)} 张图。")


if __name__ == "__main__":
    main(sys.argv[1:])
