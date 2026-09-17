from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arviz as az
import cav_common as C
import pymc as pm
import pytensor.tensor as pt

REGION_ORDER = ["额叶", "颞叶", "顶叶", "枕叶", "小脑", "脑桥"]
REF_REGION = "额叶"

SMOKE = os.environ.get("SMOKE", "0") == "1"
DRAWS = 300 if SMOKE else 2500
TUNE = 300 if SMOKE else 2500
CHAINS = 2 if SMOKE else 4
# 潜变量 + probit 选择方程的联合后验存在轻度漏斗，提高 target_accept 可显著减少发散
TARGET_ACCEPT = 0.9 if SMOKE else 0.97


# --------------------------------------------------------------------------- #
# arviz 兼容层（1.x 与 2.x 的参数名/列名差异）
# --------------------------------------------------------------------------- #
def az_summary(idata, var_names=None, hdi: float = 0.95) -> pd.DataFrame:
    """arviz 1.x 用 ci_prob/ci_kind，旧版用 hdi_prob；这里两者都兼容。"""
    params = inspect.signature(az.summary).parameters
    kw = {}
    if "ci_prob" in params:
        kw["ci_prob"] = hdi
        if "ci_kind" in params:
            kw["ci_kind"] = "hdi"
    elif "hdi_prob" in params:
        kw["hdi_prob"] = hdi
    return az.summary(idata, var_names=var_names, **kw)


def hdi_cols(df: pd.DataFrame) -> tuple[str, str]:
    """从 summary 表里取出下/上界的列名。

    兼容三种命名：``hdi_2.5% / hdi_97.5%``、``ci_2.5% / ci_97.5%``、
    ``hdi95_lb / hdi95_ub``（arviz 1.x）。
    """
    cols = list(df.columns)
    lo = next((c for c in cols if c.endswith("2.5%")), None) or next(
        (c for c in cols if c.endswith("_lb")), None
    )
    hi = next((c for c in cols if c.endswith("97.5%")), None) or next(
        (c for c in cols if c.endswith("_ub")), None
    )
    if lo is None or hi is None:  # pragma: no cover
        raise RuntimeError(f"无法从列中识别区间边界: {cols}")
    return lo, hi


# --------------------------------------------------------------------------- #
# 数据准备
# --------------------------------------------------------------------------- #
def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str], str]:
    d = C.analysis_frame(df)
    regions = [r for r in REGION_ORDER if r in set(d["region"])]
    ref = REF_REGION if REF_REGION in regions else regions[0]
    return d, regions, ref


# --------------------------------------------------------------------------- #
# 模型定义
# --------------------------------------------------------------------------- #
def build_model(
    d: pd.DataFrame, regions: list[str], *, direct_path: bool = False, tag: str = "A"
):
    """
    构建潜变量测量模型。

    ``direct_path=True`` 时额外允许 log DWI -> log SWI 的直接通路。

    注：模型的 ``loc_raw`` 以 0 为中枢先验，参照部位只影响下游报告里的
    倍数解读（见 :func:`region_table`），因此不作为参数传入。
    """
    n = len(d)
    male = d["sex"].to_numpy(float)
    age_z = d["age_z"].to_numpy(float)
    reg_idx = pd.Categorical(d["region"], categories=regions).codes.astype(int)
    log_swi = d["log_swi"].to_numpy(float)
    log_dwi = d["log_dwi"].to_numpy(float)
    log_t2 = d["log_t2"].to_numpy(float)
    t2_missing = d["t2_missing"].to_numpy(int)

    na_d = np.isnan(log_dwi)
    obs_d = ~na_d
    obs_t = ~np.isnan(log_t2)
    log_dwi0 = np.where(na_d, 0.0, log_dwi)
    age_sd = float(d["age"].std(ddof=0))

    coords = {"region": regions, "obs": np.arange(n)}
    with pm.Model(coords=coords) as model:
        # ---------------- 结构方程：外生协变量 -> 潜变量 L ------------------ #
        a_male = pm.Normal("a_male", 0.0, 0.5)
        a_age = pm.Normal("a_age", 0.0, 0.5)
        tau_loc = pm.HalfNormal("tau_loc", 0.5)
        loc_raw = pm.Normal("loc_raw", 0.0, 1.0, dims="region")
        loc_eff = pm.Deterministic("loc_eff", tau_loc * loc_raw, dims="region")

        mu = a_male * male + a_age * age_z + loc_eff[reg_idx]
        # L 的尺度固定为 1（标准化潜变量），否则与测量载荷不可识别
        L = pm.Normal("L", mu=mu, sigma=1.0, dims="obs")

        # ---------------- 测量方程（SWI 锚定载荷 = 1） --------------------- #
        nu = pm.Normal("nu", np.log(7.0), 1.0, shape=3)
        lam_d = pm.Normal("lam_d", 1.0, 0.25)
        lam_t = pm.Normal("lam_t", 1.0, 0.25)
        sd = pm.HalfNormal("sd", 0.5, shape=3)

        mu_swi = nu[0] + L
        mu_dwi = nu[1] + lam_d * L
        mu_t2 = nu[2] + lam_t * L

        mu_swi_eff = mu_swi
        delta = None
        if direct_path:
            # 对照模型 C：控制真实大小后，DWI 是否还有额外的直接效应？
            delta = pm.Normal("delta", 0.0, 0.3)
            log_dwi_full = pt.switch(pt.as_tensor(na_d), mu_dwi, pt.as_tensor(log_dwi0))
            mu_swi_eff = mu_swi + delta * log_dwi_full

        pm.Normal("swi_obs", mu=mu_swi_eff, sigma=sd[0], observed=log_swi)
        # DWI 的 2 个缺失按 MAR 用模型插补（仅参与似然的部分是观测到的）
        pm.Normal("dwi_obs", mu=mu_dwi[obs_d], sigma=sd[1], observed=log_dwi[obs_d])
        # T2WI 只在「检出」子集上建似然；因 L 已显式建模，选择在 L 上是外生的
        pm.Normal("t2_obs", mu=mu_t2[obs_t], sigma=sd[2], observed=log_t2[obs_t])

        # ---------------- MNAR 检出选择方程 ------------------------------- #
        # observed = 1 表示该病灶在 T2WI 上「被检出」；c1 > 0 表示病灶越大越易检出
        t2_detected = 1 - t2_missing
        c0 = pm.Normal("c0", 0.0, 1.5)
        c1 = pm.Normal("c1", 0.0, 1.0)
        pm.Bernoulli("t2_detect", p=pm.math.sigmoid(c0 + c1 * L), observed=t2_detected)

        # ---------------- 可解释的因果效应量 ------------------------------ #
        pm.Deterministic(
            "eff_age_10y", pt.exp(a_age * (10.0 / age_sd))
        )  # 年龄 +10 岁的乘性效应
        pm.Deterministic("eff_male", pt.exp(a_male))  # 男性 vs 女性
        # 检出概率在 L = -1 / 0 / +1 处的取值（比求解 50% 阈值更稳定）
        pm.Deterministic("p_detect_Lm1", pm.math.sigmoid(c0 - c1))
        pm.Deterministic("p_detect_L0", pm.math.sigmoid(c0))
        pm.Deterministic("p_detect_Lp1", pm.math.sigmoid(c0 + c1))
    model.name = f"model_{tag}"
    return model


def fit(model, seed: int = C.SEED):
    with model:
        idata = pm.sample(
            draws=DRAWS,
            tune=TUNE,
            chains=CHAINS,
            cores=min(CHAINS, 4),
            target_accept=TARGET_ACCEPT,
            random_seed=seed,
            progressbar=False,
            compute_convergence_checks=False,
        )
    return idata


# --------------------------------------------------------------------------- #
# 诊断
# --------------------------------------------------------------------------- #
def diagnose(idata, model, name: str) -> dict:
    s = az_summary(idata, var_names=None)
    rh = s["r_hat"].max() if "r_hat" in s.columns else np.nan
    ess_bulk = float(s["ess_bulk"].min()) if "ess_bulk" in s.columns else float("nan")
    ess_tail = float(s["ess_tail"].min()) if "ess_tail" in s.columns else float("nan")
    div = int(idata.sample_stats["diverging"].sum().item())
    out = {
        "模型": name,
        "参数数": len(s),
        "最大 R-hat": float(rh),
        "最小 ESS_bulk": ess_bulk,
        "最小 ESS_tail": ess_tail,
        "发散样本数": div,
        "收敛": bool(rh < 1.01 and ess_bulk > 400 and div == 0),
    }
    return out


# --------------------------------------------------------------------------- #
# 效应表
# --------------------------------------------------------------------------- #
def effects_table(idata, regions, ref_region) -> pd.DataFrame:
    names = [
        "a_male",
        "a_age",
        "lam_d",
        "lam_t",
        "sd",
        "c0",
        "c1",
        "tau_loc",
        "eff_age_10y",
        "eff_male",
        "p_detect_Lm1",
        "p_detect_L0",
        "p_detect_Lp1",
    ]
    s = az_summary(idata, var_names=names)
    lo, hi = hdi_cols(s)
    keep = (
        ["mean", "sd", lo, hi, "ess_bulk", "r_hat"]
        if "r_hat" in s.columns
        else ["mean", "sd", lo, hi]
    )
    out = s[keep].copy()
    out.columns = ["后验均值", "后验SD", "95%HDI 下", "95%HDI 上", "ESS_bulk", "R-hat"][
        : len(keep)
    ]
    out.index.name = "参数"
    return out


def region_table(idata, regions, ref_region) -> pd.DataFrame:
    """从 loc_eff 的后验样本直接算各部位相对参照的乘性效应（避免常量参数 R-hat=NaN）。"""
    eff = idata.posterior["loc_eff"].values.reshape(-1, len(regions))
    ref_col = regions.index(ref_region)
    ratio = np.exp(eff - eff[:, [ref_col]])
    rows = []
    for j, r in enumerate(regions):
        col = ratio[:, j]
        rows.append(
            {
                "部位": r,
                "潜变量效应(log尺度)": float(eff[:, j].mean()),
                "相对参照的倍数": float(col.mean()),
                "95%HDI 下": float(np.percentile(col, 2.5)),
                "95%HDI 上": float(np.percentile(col, 97.5)),
                "P(倍数>1)": float((col > 1).mean()),
                "为参照": r == ref_region,
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# 后验预测检验（简版，避免 arviz 绘图 API 差异）
# --------------------------------------------------------------------------- #
def ppc_check(d, model, idata) -> dict:
    try:
        with model:
            pp = pm.sample_posterior_predictive(
                idata, var_names=["swi_obs"], random_seed=C.SEED, progressbar=False
            )
        pred = pp.posterior_predictive["swi_obs"].values.reshape(-1, len(d))
        obs = d["log_swi"].to_numpy()
        in90 = np.mean(
            (obs >= np.percentile(pred, 5, axis=0))
            & (obs <= np.percentile(pred, 95, axis=0))
        )
        return {
            "观测均值": float(obs.mean()),
            "预测均值": float(pred.mean()),
            "观测SD": float(obs.std()),
            "预测SD": float(pred.std()),
            "90%区间覆盖比例": float(in90),
        }
    # 后验预测检验只是附加诊断，其失败模式取决于 PyMC/ArviZ 版本细节，
    # 无法枚举；这里有意兜底捕获，仅降级为 warn 而不中断主分析。
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        print(f"  [warn] 后验预测检验失败: {type(exc).__name__}: {exc}")
        return {}


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    df = C.load_data(verbose=False)
    d, regions, ref_region = prepare(df)
    print("=" * 78)
    print("第 3 步：PyMC 贝叶斯因果建模")
    print("=" * 78)
    print(
        f"  样本：{len(d)} 个病灶 / {d['pid'].nunique()} 位患者；"
        f"部位参照 = {ref_region}；SMOKE={SMOKE}"
    )

    # ---------------- 模型 A：共因（测量）模型 ---------------------------- #
    print("\n[3.1] 模型 A：潜变量测量模型 + MNAR 检出方程")
    mA = build_model(d, regions, direct_path=False, tag="A")
    print("  自由参数：" + ", ".join(v.name for v in mA.free_RVs))
    print("  观测变量：" + ", ".join(v.name for v in mA.observed_RVs))
    idataA = fit(mA)
    diagA = diagnose(idataA, mA, "A 共因模型")
    print(
        f"  诊断：R-hat_max={diagA['最大 R-hat']:.4f}  "
        f"ESS_min={diagA['最小 ESS_bulk']:.0f}  发散={diagA['发散样本数']}"
    )

    effA = effects_table(idataA, regions, ref_region)
    print("\n  结构/测量参数（后验均值 [95%HDI]）：")
    show = effA.copy()
    show["95%HDI"] = show.apply(
        lambda r: f"[{r['95%HDI 下']:.3f}, {r['95%HDI 上']:.3f}]", axis=1
    )
    print(show[["后验均值", "95%HDI", "R-hat"]].round(4).to_string())
    C.save_table(effA.reset_index(), "03_pymc_模型A参数.csv")

    regA = region_table(idataA, regions, ref_region)
    print("\n  部位效应（相对参照的倍数，>1 表示该部位病灶更大）：")
    print(regA.round(3).to_string(index=False))
    C.save_table(regA, "03_pymc_部位效应.csv")

    # ---------------- 模型 C：+ 直接通路 ---------------------------------- #
    print("\n[3.2] 模型 C：在模型 A 上允许 log DWI -> log SWI 直接通路（delta）")
    mC = build_model(d, regions, direct_path=True, tag="C")
    idataC = fit(mC)
    diagC = diagnose(idataC, mC, "C +直接通路")
    dl = idataC.posterior["delta"].values.ravel()
    d_lo, d_hi = np.percentile(dl, [2.5, 97.5])
    d_mean = float(dl.mean())
    # 后验中 delta 落在「等效零区」(|delta|<0.1) 的比例
    p_rope = float(np.mean(np.abs(dl) < 0.1))
    print(
        f"  delta 后验 = {d_mean:.3f} [95%HDI {d_lo:.3f}, {d_hi:.3f}]；"
        f"P(|delta|<0.1) = {p_rope:.3f}"
    )
    covered = d_lo < 0 < d_hi
    # delta 的识别性诊断：若 A->C 中载荷 lam_d 明显位移，说明 delta 在掠夺 L 的解释力，
    # 此时 delta 不能解释为「直接因果效应」（典型的潜变量-回归量 trade-off）。
    lamA = idataA.posterior["lam_d"].values.ravel()
    lamC = idataC.posterior["lam_d"].values.ravel()
    lamA_lo, lamA_hi = np.percentile(lamA, [2.5, 97.5])
    lamC_lo, lamC_hi = np.percentile(lamC, [2.5, 97.5])
    shift = float(lamC.mean() - lamA.mean())
    print(
        f"  lam_d：A {lamA.mean():.3f} [{lamA_lo:.3f}, {lamA_hi:.3f}]  vs  "
        f"C {lamC.mean():.3f} [{lamC_lo:.3f}, {lamC_hi:.3f}]（位移 {shift:+.3f}）"
    )
    print(
        f"  -> delta 的 95%HDI {'覆盖' if covered else '不覆盖'} 0；"
        + (
            "共因结构已足以解释 DWI 与 SWI 的强相关。"
            if covered
            else "但控制 L 后仍留下非零的直接项。"
        )
    )
    if abs(shift) > 0.1:
        print(
            "  注意：把 log DWI 同时当作 L 的指标又当作 log SWI 的解释变量会与 L 的载荷"
            "互相争夺解释力（trade-off），因此 delta 不应直接读作因果效应；"
            "此处以模型 A 的载荷（≈1）作为主结论。"
        )

    # ---------------- 模型比较 -------------------------------------------- #
    print("\n[3.3] 模型比较（ELPD / LOO）")
    cmp_rows = []
    try:
        for model, idata, lab in ((mA, idataA, "A 共因"), (mC, idataC, "C 直接通路")):
            pm.compute_log_likelihood(
                idata, model=model, extend_inferencedata=True, progressbar=False
            )
        comp = az.compare({"A 共因": idataA, "C 直接通路": idataC})
        print(comp.round(3).to_string())
        cmp_rows = (
            comp.reset_index().rename(columns={"index": "模型"}).to_dict("records")
        )
        C.save_table(comp.reset_index(), "03_pymc_模型比较.csv")
    # LOO 模型比较是可选增强（arviz 1.x 对 DataTree 的支持仍在变动），
    # 失败时降级为只报告 delta 的后验区间。
    except Exception as exc:  # noqa: BLE001
        print(f"  [warn] LOO 比较不可用（{type(exc).__name__}: {exc}），")
        print("         以 delta 的后验区间为主要判据。")

    # ---------------- 后验预测检验 ---------------------------------------- #
    print("\n[3.4] 后验预测检验（log SWI）")
    ppc = ppc_check(d, mA, idataA)
    if ppc:
        for k, v in ppc.items():
            print(f"  {k}: {v:.3f}")

    # ---------------- 绘图输入（供 plots_pymc_causal.py 免重采样使用）------ #
    L_mean = idataA.posterior["L"].values.reshape(-1, len(d)).mean(axis=0)
    C.save_table(
        pd.DataFrame(
            {
                "序号": np.arange(len(d)),
                "L后验均值": L_mean,
                "log_t2": d["log_t2"].to_numpy(),
                "log_dwi": d["log_dwi"].to_numpy(),
                "log_swi": d["log_swi"].to_numpy(),
            }
        ),
        "03_pymc_潜变量后验.csv",
    )
    C.save_table(
        pd.DataFrame({"delta": dl, "lam_d_A": lamA, "lam_d_C": lamC}),
        "03_pymc_关键参数后验样本.csv",
    )

    # ---------------- 汇总 ------------------------------------------------ #
    diag_df = pd.DataFrame([diagA, diagC])
    C.save_table(diag_df, "03_pymc_收敛诊断.csv")
    res = {
        "model_A_params": effA.reset_index().to_dict("records"),
        "model_A_region_effects": regA.to_dict("records"),
        "model_C_delta": {
            "mean": d_mean,
            "hdi_low": float(d_lo),
            "hdi_high": float(d_hi),
            "p_rope_0.1": p_rope,
            "covers_zero": bool(covered),
            "lam_d_shift_vs_A": float(shift),
            # 模型 C 里 lam_d 的点估计（= A 的均值 + 位移）。报告叙述要显示它，
            # 因此在这里算好落盘，报告端不做加法。
            "lam_d_in_C": float(lamC.mean()),
        },
        "model_comparison": cmp_rows,
        "diagnostics": [diagA, diagC],
        "ppc": ppc,
        "sampler": {"draws": DRAWS, "tune": TUNE, "chains": CHAINS, "smoke": SMOKE},
    }
    C.save_results(res, "03_pymc_results.csv")

    lam_d = effA.loc["lam_d"]
    lam_t = effA.loc["lam_t"]
    age_eff = effA.loc["eff_age_10y"]

    print("\n" + "=" * 78)
    print("第 3 步完成。关键结论：")
    print(
        f"  · DWI 与 SWI 的载荷比 = {lam_d['后验均值']:.3f}"
        f" [95%HDI {lam_d['95%HDI 下']:.3f}, {lam_d['95%HDI 上']:.3f}]（SWI 锚定 = 1）"
    )
    print(
        f"  · T2WI 载荷 = {lam_t['后验均值']:.3f}"
        f" [95%HDI {lam_t['95%HDI 下']:.3f}, {lam_t['95%HDI 上']:.3f}]（相对 SWI 略低估）"
    )
    print(
        f"  · 直接通路 delta = {d_mean:.3f} [95%HDI {d_lo:.3f}, {d_hi:.3f}]"
        f" -> {'与 0 不可区分' if covered else '不包含 0'}"
    )
    print(
        f"  · 年龄 +10 岁对真实大小的乘性效应 = {age_eff['后验均值']:.3f}"
        f" [95%HDI {age_eff['95%HDI 下']:.3f}, {age_eff['95%HDI 上']:.3f}]"
    )
    print(
        "  · 识别性局限：三变量的单因子模型 df=0（恰好识别），"
        "本设计无法用拟合优度支持/证伪共因假设；"
        "要区分共因与直接通路至少需要第 4 个独立指标。"
    )
    print("  数值已落盘；图形请运行 python src/plots_pymc_causal.py")
    print("=" * 78)


if __name__ == "__main__":
    main()
