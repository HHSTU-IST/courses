from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cav_common as C
import matplotlib.pyplot as plt

GL_VARS = ["log_t2", "log_dwi", "log_swi", "age_z", "sex", "supra"]


# =========================================================================== #
# 图 01：缺失结构
# =========================================================================== #
def fig01_missingness(df: pd.DataFrame, res: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    ax = axes[0]
    miss = pd.Series(
        {
            "T2WI": df.t2_missing.sum(),
            "DWI": df.dwi_missing.sum(),
            "SWI": df.swi_missing.sum(),
        }
    )
    ax.bar(miss.index, miss.values, color=["#c0392b", "#e67e22", "#2980b9"])
    for i, v in enumerate(miss.values):
        ax.text(i, v + 0.15, f"{v}/{len(df)}", ha="center", fontsize=9)
    ax.set_ylabel(C.L("未检出病灶数", "Not-detected lesions"))
    ax.set_title(C.L("(a) 各序列未检出（缺失）例数", "(a) Missingness by sequence"))
    ax.set_ylim(0, max(miss.values) * 1.25)

    ax = axes[1]
    ok = df[df.t2_missing == 0]
    bad = df[df.t2_missing == 1]
    ax.scatter(
        ok.dwi,
        ok.swi,
        s=42,
        c="#2980b9",
        edgecolor="white",
        label=C.L("T2WI 检出", "T2WI detected"),
        zorder=3,
    )
    ax.scatter(
        bad.dwi,
        bad.swi,
        s=52,
        c="#c0392b",
        marker="^",
        edgecolor="white",
        label=C.L("T2WI 未检出", "T2WI not detected"),
        zorder=3,
    )
    lim = [2.5, np.nanmax(df.swi) * 1.08]
    ax.plot(lim, lim, "--", c="grey", lw=1)
    ax.set_xlim(lim)
    ax.set_ylim(lim)
    ax.set_xlabel("DWI (mm)")
    ax.set_ylabel("SWI (mm)")
    ax.set_title(
        C.L(
            "(b) DWI–SWI 散点：缺失集中在左下角（小病灶）",
            "(b) DWI vs SWI; missingness concentrated at small sizes",
        )
    )
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout()
    return C.savefig(fig, "fig01_missingness.png")


# =========================================================================== #
# 图 02：分布
# =========================================================================== #
def fig02_distributions(df: pd.DataFrame, res: dict) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.9))
    ax = axes[0]
    ax.hist(df.age.dropna(), bins=12, color="#8e44ad", alpha=0.85, edgecolor="white")
    ax.set_xlabel(C.L("年龄（岁）", "Age (years)"))
    ax.set_ylabel(C.L("例数", "count"))
    ax.set_title(C.L("(a) 年龄分布", "(a) Age"))

    ax = axes[1]
    data = [df[c].dropna().to_numpy() for c in ("t2", "dwi", "swi")]
    bp = C.boxplot(
        ax, data, tick_labels=["T2WI", "DWI", "SWI"], patch_artist=True, widths=0.6
    )
    for patch, col in zip(bp["boxes"], ["#c0392b", "#e67e22", "#2980b9"]):
        patch.set_facecolor(col)
        patch.set_alpha(0.75)
    for i, d in enumerate(data, start=1):
        ax.scatter(
            np.full(len(d), i) + np.random.default_rng(0).normal(0, 0.06, len(d)),
            d,
            s=14,
            c="k",
            alpha=0.55,
            zorder=3,
        )
    ax.set_ylabel(C.L("最大径 (mm)", "Max diameter (mm)"))
    ax.set_title(C.L("(b) 三序列测量分布", "(b) Sizes by sequence"))

    ax = axes[2]
    regs = [
        r
        for r in df.region.value_counts().index
        if df.loc[df.region == r, "swi"].notna().any()
    ]
    box = [df.loc[df.region == r, "swi"].dropna().to_numpy() for r in regs]
    C.boxplot(ax, box, tick_labels=[C.L(r, r) for r in regs], patch_artist=True)
    ax.set_ylabel("SWI (mm)")
    ax.set_title(C.L("(c) SWI 按解剖分区", "(c) SWI by region"))
    ax.tick_params(axis="x", labelrotation=30)
    fig.tight_layout()
    return C.savefig(fig, "fig02_distributions.png")


# =========================================================================== #
# 图 03：相关系数矩阵（读 01_Pearson相关.csv / 01_Spearman相关.csv）
# =========================================================================== #
def fig03_correlation(df: pd.DataFrame, res: dict) -> Path:
    pear = C.read_table("01_Pearson相关.csv", index_col="变量")
    spear = C.read_table("01_Spearman相关.csv", index_col="变量")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.0), layout="constrained")
    for ax, mat, ttl in ((axes[0], pear, "Pearson"), (axes[1], spear, "Spearman")):
        im = ax.imshow(mat.values, vmin=-1, vmax=1, cmap="RdBu_r")
        labs = [C.plot_label(c) for c in mat.columns]
        ax.set_xticks(range(len(mat)), labs, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(mat)), labs, fontsize=8)
        for i in range(len(mat)):
            for j in range(len(mat)):
                ax.text(
                    j,
                    i,
                    f"{mat.values[i, j]:.2f}",
                    ha="center",
                    va="center",
                    fontsize=7.5,
                    color="white" if abs(mat.values[i, j]) > 0.6 else "black",
                )
        ax.set_title(f"{ttl} " + C.L("相关（对数尺度）", "correlation (log scale)"))
        ax.grid(False)
    fig.colorbar(im, ax=axes, shrink=0.8)
    return C.savefig(fig, "fig03_correlation.png")


# =========================================================================== #
# 图 04：不同设定下的弹性（读 02_sklearn_results.csv）
# =========================================================================== #
def fig04_elasticity(df: pd.DataFrame, res: dict) -> Path:
    dml = res["dml"]

    def ci(key: str) -> tuple[float, float]:
        """置信区间在结果长表里是「<键>.下」「<键>.上」两行，读回来是字典。"""
        d = res[key]
        return d["下"], d["上"]

    items = [
        (f"M1 仅 DWI (n={res['n_obs_dwi_swi']})", res["naive_beta"], *ci("naive_ci")),
        (f"M2 +观测混杂 (n={res['n_obs_dwi_swi']})", res["adj_beta"], *ci("adj_ci")),
        (
            f"M3 +log T2WI (n={res['n_complete_t2']})",
            res["proxy_beta"],
            *ci("proxy_ci"),
        ),
        (f"M4 DML (n={dml['n']})", dml["theta"], dml["ci95_low"], dml["ci95_high"]),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    ys = np.arange(len(items))[::-1]
    for ypos, (lab, b, lo, hi) in zip(ys, items):
        ax.errorbar(
            b,
            ypos,
            xerr=[[b - lo], [hi - b]],
            fmt="o",
            ms=7,
            color="#2980b9",
            capsize=4,
            lw=1.8,
        )
        ax.text(hi + 0.04, ypos, f"{b:.3f}", va="center", fontsize=9)
    ax.axvline(1.0, ls="--", c="grey", lw=1)
    ax.axvline(0.0, ls=":", c="#c0392b", lw=1)
    ax.set_yticks(ys, [i[0] for i in items], fontsize=9)
    ax.set_xlabel(
        C.L("log DWI 对 log SWI 的系数（弹性）", "coefficient of log DWI on log SWI")
    )
    ax.set_title(
        C.L(
            "DWI→SWI 关联随控制变量的变化（95% 自助 CI）",
            "DWI→SWI association across specifications (95% bootstrap CI)",
        )
    )
    fig.tight_layout()
    return C.savefig(fig, "fig04_elasticity_compare.png")


# =========================================================================== #
# 图 05：边际相关 vs 偏相关（偏相关读 02_偏相关矩阵.csv，边际相关由数据框直接算）
# =========================================================================== #
def fig05_partial_corr(df: pd.DataFrame, res: dict) -> Path:
    marg = df.dropna(subset=["log_t2", "log_dwi", "log_swi"])[GL_VARS].corr()
    pcorr = C.read_table("02_偏相关矩阵.csv", index_col="变量")
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.3), layout="constrained")
    for ax, mat, ttl in (
        (axes[0], marg, C.L("边际相关", "Marginal correlation")),
        (
            axes[1],
            pcorr,
            C.L("偏相关（条件独立）", "Partial correlation (cond. indep.)"),
        ),
    ):
        v = mat.values
        im = ax.imshow(v, vmin=-1, vmax=1, cmap="RdBu_r")
        labs = [C.plot_label(c) for c in mat.columns]
        ax.set_xticks(range(len(labs)), labs, rotation=45, ha="right", fontsize=8)
        ax.set_yticks(range(len(labs)), labs, fontsize=8)
        for i in range(len(labs)):
            for j in range(len(labs)):
                ax.text(
                    j,
                    i,
                    f"{v[i, j]:.2f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if abs(v[i, j]) > 0.6 else "black",
                )
        ax.set_title(ttl, fontsize=10.5)
        ax.grid(False)
    fig.colorbar(im, ax=axes, shrink=0.85)
    return C.savefig(fig, "fig05_partial_corr.png")


# =========================================================================== #
# 图 06：特征重要性与预测性能（读 02_置换重要性.csv / 02_CV性能.csv）
# =========================================================================== #
def fig06_importance(df: pd.DataFrame, res: dict) -> Path:
    imp = C.read_table("02_置换重要性.csv")
    perf = C.read_table("02_CV性能.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
    ax = axes[0]
    d = imp.sort_values("重要性均值")
    ax.barh(
        [C.plot_label(c) for c in d["特征"]],
        d["重要性均值"],
        xerr=d["SD"],
        color="#16a085",
        alpha=0.85,
        capsize=3,
    )
    ax.axvline(0, c="k", lw=0.8)
    ax.set_xlabel(C.L("置换重要性（R² 下降）", "Permutation importance (R² drop)"))
    ax.set_title(
        C.L(
            "(a) 随机森林预测 log SWI 的特征重要性",
            "(a) RF permutation importance for log SWI",
        )
    )
    ax = axes[1]
    ax.barh(
        perf["特征集"],
        perf["CV R2 均值"],
        xerr=perf["CV R2 SD"],
        color="#8e44ad",
        alpha=0.85,
        capsize=3,
    )
    ax.set_xlim(0, 1)
    ax.set_xlabel(C.L("5×10 折交叉验证 R²", "Repeated 5-fold CV R²"))
    ax.set_title(
        C.L("(b) 不同特征集的样本外预测能力", "(b) Out-of-sample R² by feature set")
    )
    ax.tick_params(axis="y", labelsize=8)
    fig.tight_layout()
    return C.savefig(fig, "fig06_importance.png")


# =========================================================================== #
# 图 07：单因子模型（读 02_单因子模型.csv）
# =========================================================================== #
def fig07_factor(df: pd.DataFrame, res: dict) -> Path:
    fa_df = C.read_table("02_单因子模型.csv")
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6))
    ax = axes[0]
    ax.bar(fa_df["指标"], fa_df["载荷"], color="#2980b9", alpha=0.85)
    ax.set_ylabel(C.L("因子载荷（标准化）", "factor loading"))
    ax.set_title(C.L("(a) 单因子载荷", "(a) Single-factor loadings"))
    ax = axes[1]
    x = np.arange(len(fa_df))
    ax.bar(
        x - 0.2,
        fa_df["共同方差占比(=信度)"],
        width=0.4,
        label=C.L("共同方差(信度)", "common"),
        color="#27ae60",
        alpha=0.85,
    )
    ax.bar(
        x + 0.2,
        fa_df["独特方差(噪声)"],
        width=0.4,
        label=C.L("独特方差(噪声)", "unique"),
        color="#c0392b",
        alpha=0.85,
    )
    ax.set_xticks(x, fa_df["指标"])
    ax.set_ylim(0, 1.05)
    ax.set_title(C.L("(b) 方差分解", "(b) Variance decomposition"))
    # 两类条形加起来恒等于 1，坐标区内没有空隙可放图例
    # （放右上角会压在最后一组柱子上），因此放到坐标区下方。
    ax.legend(
        frameon=False,
        fontsize=8.5,
        ncol=2,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
    )
    fig.tight_layout()
    return C.savefig(fig, "fig07_factor_analysis.png")


# =========================================================================== #
# 图 08：MNAR 缺失机制（读 01_缺失机制检验.csv / 02_缺失机制逻辑回归.csv）
# =========================================================================== #
def fig08_mnar(df: pd.DataFrame, res: dict) -> Path:
    mnar = C.read_table("01_缺失机制检验.csv")
    # 系数与 AUC 取自结果长表（与报告同源，只有一个来源）；p 值只在表 CSV 里，
    # 标题只取到小数点后 3 位，无碍。
    # 注意：结果长表的落盘精度是 ROUND_DIGITS（4 位），坐标轴自动缩放会因此与
    # 更早期用全精度值渲染出的图差出亚像素级漂移（0.2% 像素、肉眼不可辨）。
    # 这是既有的落盘精度现象，不是渲染出错；重跑绘图脚本即得新版，结论不变。
    p_min = float(mnar["p值"].min())
    coefs = [res["mnar_coef"]["log_dwi"], res["mnar_coef"]["log_swi"]]
    auc = float(res["mnar_auc"])

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.6))
    ax = axes[0]
    g1 = df.loc[df.t2_missing == 1]  # T2WI 未检出该病灶
    g0 = df.loc[df.t2_missing == 0]  # T2WI 检出该病灶
    C.boxplot(
        ax,
        [g1.dwi.dropna(), g0.dwi.dropna(), g1.swi.dropna(), g0.swi.dropna()],
        tick_labels=[
            C.L("DWI\n(T2 未检出)", "DWI\n(T2 missed)"),
            C.L("DWI\n(T2 检出)", "DWI\n(T2 seen)"),
            C.L("SWI\n(T2 未检出)", "SWI\n(T2 missed)"),
            C.L("SWI\n(T2 检出)", "SWI\n(T2 seen)"),
        ],
        patch_artist=True,
    )
    ax.set_ylabel("mm")
    ax.set_title(
        C.L(
            f"(a) T2WI 缺失组的病灶更小（p={p_min:.3f}）",
            f"(a) Smaller lesions where T2WI missing (p={p_min:.3f})",
        ),
        fontsize=10,
    )
    ax.tick_params(axis="x", labelsize=8)

    ax = axes[1]
    ax.bar(["log DWI", "log SWI"], coefs, color=["#e67e22", "#2980b9"], alpha=0.85)
    ax.axhline(0, c="k", lw=0.8)
    ax.set_ylabel(C.L("标准化 logit 系数", "standardized logit coef."))
    ax.set_title(
        C.L(
            f"(b) 未检出的逻辑回归（CV AUC={auc:.2f}）",
            f"(b) Non-detection logistic model (CV AUC={auc:.2f})",
        ),
        fontsize=10,
    )
    fig.tight_layout()
    return C.savefig(fig, "fig08_mnar.png")


# =========================================================================== #
FIGS: dict[str, Callable[[pd.DataFrame, dict], Path]] = {
    "fig01": fig01_missingness,
    "fig02": fig02_distributions,
    "fig03": fig03_correlation,
    "fig04": fig04_elasticity,
    "fig05": fig05_partial_corr,
    "fig06": fig06_importance,
    "fig07": fig07_factor,
    "fig08": fig08_mnar,
}


def main(want: Sequence[str] | None = None) -> None:
    names = list(FIGS) if not want else [n for n in want if n in FIGS]
    unknown = [n for n in (want or []) if n not in FIGS]
    if unknown:
        raise SystemExit(f"未知的图名 {unknown}；可选：{', '.join(FIGS)}")
    if not names:
        return
    C.setup_matplotlib()
    print("=" * 78)
    print("绘图：第 1、2 步（只读 data，不重跑建模）")
    print("=" * 78)
    df = C.analysis_frame(verbose=False)
    res = C.load_results("02_sklearn_results.csv")
    for n in names:
        FIGS[n](df, res)
    print(f"完成，共 {len(names)} 张图。")


if __name__ == "__main__":
    main(sys.argv[1:])
