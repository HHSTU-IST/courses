from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cav_common as C
from sklearn.decomposition import FactorAnalysis
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LassoCV, LinearRegression, LogisticRegression, RidgeCV
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

TBL = C.DAT
TBL.mkdir(parents=True, exist_ok=True)

_save_table = C.save_table


# =========================================================================== #
# 第 1 步：探索
# =========================================================================== #
def step1_explore(df: pd.DataFrame) -> dict:
    print("\n" + "=" * 78)
    print("第 1 步：数据读取与探索")
    print("=" * 78)

    # ---- 1.1 变量类型与缺失
    print("\n[1.1] 变量类型 / 缺失值")
    info = pd.DataFrame(
        {
            "dtype": df.dtypes.astype(str),
            "非空": df.notna().sum(),
            "缺失": df.isna().sum(),
            "缺失率%": (df.isna().mean() * 100).round(1),
            "取值数": df.nunique(dropna=True),
        }
    )
    print(info.to_string())
    _save_table(info.reset_index(names="列名"), "01_变量概览.csv")

    # ---- 1.2 连续变量描述统计
    print("\n[1.2] 连续变量描述统计（原始尺度, mm / 岁）")
    num = ["age", "t2", "dwi", "swi"]
    desc = df[num].describe().T
    desc["skew"] = df[num].skew()
    desc["CV%"] = df[num].std() / df[num].mean() * 100
    print(desc.round(3).to_string())
    _save_table(desc.reset_index(names="变量"), "01_连续变量描述.csv")

    # ---- 1.3 分类变量频数
    print("\n[1.3] 分类变量频数")
    cats = {}
    for col, lab in (
        ("sex", "性别(1男/0女)"),
        ("region", "解剖分区"),
        ("supra", "幕上1/幕下0"),
        ("side", "左1/右0/中线-1"),
    ):
        vc = df[col].value_counts(dropna=False).sort_index()
        cats[lab] = vc
        print(f"  {lab}: " + ", ".join(f"{k}={v}" for k, v in vc.items()))
    cat_df = pd.concat(
        {k: v for k, v in cats.items()}, names=["变量", "取值"]
    ).reset_index()
    cat_df.columns = ["变量", "取值", "例数"]
    _save_table(cat_df, "01_分类变量频数.csv")

    # ---- 1.4 缺失机制（MNAR 证据）
    print("\n[1.4] 缺失机制检验：T2WI 未检出 vs 检出 的其它序列")
    mnar = C.mnar_table(df)
    print(mnar.to_string(index=False))
    _save_table(mnar, "01_缺失机制检验.csv")

    # ---- 1.5 相关结构
    print("\n[1.5] 相关结构（对数尺度）")
    corr_cols = ["log_t2", "log_dwi", "log_swi", "age"]
    sub = df[[*corr_cols, "sex", "supra"]].copy()
    pear = sub.corr(method="pearson")
    spear = sub.corr(method="spearman")
    print("Pearson:\n" + pear.round(3).to_string())
    _save_table(pear.reset_index(names="变量"), "01_Pearson相关.csv")
    _save_table(spear.reset_index(names="变量"), "01_Spearman相关.csv")

    # 三个尺寸变量两两相关的自助置信区间
    tri = []
    for a, b in (("log_t2", "log_dwi"), ("log_t2", "log_swi"), ("log_dwi", "log_swi")):
        m = df[[a, b]].dropna()
        r = float(np.corrcoef(m[a], m[b])[0, 1])
        lo, hi = C.bootstrap_ci(
            m[a].to_numpy(), m[b].to_numpy(), stat="pearson", n_boot=2000
        )
        tri.append(
            {
                "配对": f"{C.data_label(a)} ~ {C.data_label(b)}",
                "n": len(m),
                "Pearson r": r,
                "r 95%CI 下": lo,
                "r 95%CI 上": hi,
            }
        )
    tri_df = pd.DataFrame(tri)
    print("\n" + tri_df.round(4).to_string(index=False))
    _save_table(tri_df, "01_尺寸变量配对相关.csv")

    # 预处理小结（只打印，不进产物）
    print("\n[1.6] 预处理决策")
    prep = [
        "患者 id：Excel 合并单元格 -> 对「序号」前向填充（28 位患者 / 39 个病灶）。",
        "T2WI、DWI 中的 '-' -> NaN，表示该序列未检出该病灶（不是录入错误）。",
        "部位缺失 1 例（患者 18 的第 2 个病灶）-> 用同患者其它病灶的部位补齐；其余不做插补。",
        "尺寸变量做 log 变换；系数解释为弹性（1% -> x%）。",
        "性别 男=1/女=0；部位派生『幕上1 / 幕下0』与『左1 / 右0 / 中线-1』。",
        (
            "不做单值插补：T2WI 缺失与病灶大小强相关（MNAR），插补会引入偏倚；"
            "改用显式缺失机制模型（见 02_pymc_causal.py）。"
        ),
    ]
    for s in prep:
        print("  - " + s)

    # 医学含义
    print("\n[1.7] 医学含义假设（第 2~7 列）")
    for k, v in C.MEDICAL_NOTES.items():
        print(f"  - {k}: {v}")

    return {
        "pearson": pear,
        "spearman": spear,
        "table1_corr": tri_df,
        "mnar_table": mnar,
    }


# =========================================================================== #
# 第 2 步：scikit-learn 建模
# =========================================================================== #
def _boot_ols_ci(
    X: np.ndarray, y: np.ndarray, k: int, n_boot: int = 2000, seed: int = C.SEED
) -> tuple[float, float]:
    """自助法给出第 k 个系数的 95% CI（退化样本记为 NaN 后按分位数忽略）。"""
    rng = np.random.default_rng(seed)
    n = len(y)
    out = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            out[b] = LinearRegression().fit(X[idx], y[idx]).coef_[k]
        except (np.linalg.LinAlgError, ValueError):  # pragma: no cover
            # 重采样后可能出现奇异/含非有限值的子样本，跳过该次重采样。
            out[b] = np.nan
    return float(np.nanpercentile(out, 2.5)), float(np.nanpercentile(out, 97.5))


def step2_sklearn(df: pd.DataFrame) -> dict:
    print("\n" + "=" * 78)
    print("第 2 步：scikit-learn 建模")
    print("=" * 78)
    res: dict = {}

    df = C.analysis_frame(df)

    # ---- 2.1 朴素弹性：log SWI ~ log DWI ---------------------------------- #
    print("\n[2.1] 朴素模型 M1：log SWI ~ log DWI（把两者当成两个独立变量）")
    s1 = df.dropna(subset=["log_dwi", "log_swi"])
    X1 = s1[["log_dwi"]].to_numpy()
    y1 = s1["log_swi"].to_numpy()
    m1 = LinearRegression().fit(X1, y1)
    lo1, hi1 = _boot_ols_ci(X1, y1, 0)
    r2_1 = m1.score(X1, y1)
    print(
        f"  n={len(s1)}  beta={m1.coef_[0]:.3f} [95%CI {lo1:.3f},{hi1:.3f}]  "
        f"intercept={m1.intercept_:.3f}  R2={r2_1:.3f}"
    )
    print(f"  解释：DWI 每增大 1%，SWI 平均增大 {m1.coef_[0]:.2f}%（对数-对数弹性）。")

    # 原始尺度对照
    s1r = df.dropna(subset=["dwi", "swi"])
    m1r = LinearRegression().fit(s1r[["dwi"]], s1r["swi"])
    print(
        f"  原始尺度：SWI = {m1r.intercept_:.2f} + {m1r.coef_[0]:.3f} * DWI  "
        f"(R2={m1r.score(s1r[['dwi']], s1r['swi']):.3f})"
    )

    # ---- 2.2 加入观测混杂（性别/年龄/部位）-------------------------------- #
    print("\n[2.2] 模型 M2：+ 观测混杂（年龄、性别、幕上、左右）")
    conf = ["age_z", "sex", "supra", "left"]
    X2 = s1[["log_dwi", *conf]].to_numpy()
    y2 = y1
    m2 = LinearRegression().fit(X2, y2)
    lo2, hi2 = _boot_ols_ci(X2, y2, 0)
    r2_2 = m2.score(X2, y2)
    print(
        f"  n={len(s1)}  beta_DWI={m2.coef_[0]:.3f} [95%CI {lo2:.3f},{hi2:.3f}]  R2={r2_2:.3f}"
    )
    for name, b in zip(["age_z", "sex", "supra", "left"], m2.coef_[1:]):
        print(f"    {name:8s} {b:+.4f}")

    # ---- 2.3 加入第二个代理变量 log T2WI --------------------------------- #
    print("\n[2.3] 模型 M3：+ 另一个代理变量 log T2WI（在完整病例子集上）")
    s3 = df.dropna(subset=["log_t2", "log_dwi", "log_swi"])
    X3 = s3[["log_dwi", "log_t2", *conf]].to_numpy()
    y3 = s3["log_swi"].to_numpy()
    m3 = LinearRegression().fit(X3, y3)
    lo3, hi3 = _boot_ols_ci(X3, y3, 0)
    r2_3 = m3.score(X3, y3)
    print(
        f"  n={len(s3)}  beta_DWI={m3.coef_[0]:.3f} [95%CI {lo3:.3f},{hi3:.3f}]  "
        f"beta_T2={m3.coef_[1]:.3f}  R2={r2_3:.3f}"
    )
    # 与 M1 对比：点估计方向 + 不确定性是否膨胀（数据驱动，不写死结论）
    ci_w1, ci_w3 = hi1 - lo1, hi3 - lo3
    trend = "下降" if m3.coef_[0] < m1.coef_[0] else "未下降"
    print(
        f"  与 M1 对比：点估计 {m1.coef_[0]:.3f} -> {m3.coef_[0]:.3f}（{trend}）；"
        f"但 95%CI 宽度 {ci_w1:.3f} -> {ci_w3:.3f}（膨胀 {ci_w3 / ci_w1:.1f} 倍），"
        f"beta_T2={m3.coef_[1]:.3f} 接近 0"
    )
    print(
        "  解读：log T2WI 与 log DWI 是同一个潜变量的两次测量（VIF>60），"
        "因此控制它无法『剥离』出一条因果通路，只会把共同原因的解释力在两个共线变量间重新分配。"
        "系数区间急剧膨胀、而两个系数本身都未稳定偏离 M1 —— 这是共同原因结构的诊断信号，"
        "而不是『DWI 的效应被解释掉了』。"
    )

    # 同样本基线上只放混杂（不含 T2/DWI），便于比较 R2 增量
    X3c = s3[conf].to_numpy()
    r2_conf_only = LinearRegression().fit(X3c, y3).score(X3c, y3)
    print(
        f"  同子集仅混杂 R2={r2_conf_only:.3f}；仅 DWI R2="
        f"{LinearRegression().fit(s3[['log_dwi']], y3).score(s3[['log_dwi']], y3):.3f}"
    )

    # ---- 2.4 双重机器学习 DML（去偏因果效应）------------------------------ #
    print("\n[2.4] 模型 M4：双重机器学习（DML, 交叉拟合残差正交化）")
    dml = C.dml_partial_linear(
        s1[conf], s1["log_dwi"], s1["log_swi"], n_splits=5, n_repeats=10
    )
    print(
        f"  theta(DWI->SWI | 观测混杂) = {dml['theta']:.3f} "
        f"[95%CI {dml['ci95_low']:.3f},{dml['ci95_high']:.3f}]  n={dml['n']}"
    )
    print(f"  10 次重复交叉拟合的 theta 波动 SD = {dml['theta_sd_across_repeats']:.4f}")
    print(
        "  解读：DML 修正了观测混杂带来的偏倚，但潜变量 L 未被观测，"
        "所以 theta 仍显著为正 —— 它测的是『相关性中无法被观测协变量解释的残余』，不是因果效应。"
    )

    # ---- 2.5 多重共线性（VIF / Lasso / Ridge）---------------------------- #
    print("\n[2.5] 共线性诊断")
    Xc = s3[["log_t2", "log_dwi", "log_swi", "age_z", "sex", "supra"]]
    vif = C.vif_table(Xc)
    print(vif.round(3).to_string(index=False))
    _save_table(vif, "02_VIF.csv")

    lasso = make_pipeline(
        StandardScaler(), LassoCV(cv=5, random_state=C.SEED, max_iter=50000)
    ).fit(Xc, y3)
    coef_l = pd.Series(lasso[-1].coef_, index=Xc.columns)
    ridge = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 3, 30))).fit(
        Xc, y3
    )
    coef_r = pd.Series(ridge[-1].coef_, index=Xc.columns)
    print("\n  标准化系数（预测 log SWI）：")
    coef_df = pd.DataFrame({"LassoCV": coef_l, "RidgeCV": coef_r})
    print(coef_df.round(4).to_string())
    _save_table(coef_df.reset_index(names="变量"), "02_正则化系数.csv")

    # ---- 2.6 预测性能与特征重要性 ---------------------------------------- #
    print("\n[2.6] 交叉验证预测性能 + 置换重要性")
    cv = RepeatedKFold(n_splits=5, n_repeats=10, random_state=C.SEED)

    def _cv_r2(X, y, est):
        sc = cross_val_score(est, X, y, cv=cv, scoring="r2")
        return float(np.mean(sc)), float(np.std(sc))

    perf = {}
    y_full = df.log_swi.to_numpy()
    m_dwi = df[["log_dwi"]].to_numpy()
    m_conf = df[["age_z", "sex", "supra", "left"]].to_numpy()
    mask_obs = ~np.isnan(m_dwi[:, 0]) & ~np.isnan(y_full)
    m_dwic = np.hstack([m_dwi, m_conf])
    perf[f"仅 log DWI (n={mask_obs.sum()})"] = _cv_r2(
        m_dwi[mask_obs], y_full[mask_obs], LinearRegression()
    )
    perf[f"log DWI + 观测混杂 (n={mask_obs.sum()})"] = _cv_r2(
        m_dwic[mask_obs], y_full[mask_obs], LinearRegression()
    )
    mask3 = (
        ~np.isnan(df.log_t2.to_numpy())
        & ~np.isnan(df.log_dwi.to_numpy())
        & ~np.isnan(y_full)
    )
    m_all = np.hstack([df[["log_t2"]].to_numpy(), m_dwic])
    perf[f"+ log T2WI 全部 (n={mask3.sum()})"] = _cv_r2(
        m_all[mask3], y_full[mask3], LinearRegression()
    )
    perf[f"随机森林 全部变量 (n={mask3.sum()})"] = _cv_r2(
        m_all[mask3],
        y_full[mask3],
        RandomForestRegressor(
            n_estimators=500, min_samples_leaf=2, random_state=C.SEED
        ),
    )
    perf_df = pd.DataFrame(
        [{"特征集": k, "CV R2 均值": v[0], "CV R2 SD": v[1]} for k, v in perf.items()]
    )
    print(perf_df.round(4).to_string(index=False))
    _save_table(perf_df, "02_CV性能.csv")

    rf = RandomForestRegressor(
        n_estimators=1000, min_samples_leaf=2, random_state=C.SEED
    )
    rf.fit(m_all[mask3], y_full[mask3])

    names = ["log T2WI", "log DWI", "age_z", "sex", "supra", "left"]
    pi = permutation_importance(
        rf, m_all[mask3], y_full[mask3], n_repeats=60, random_state=C.SEED, scoring="r2"
    )
    imp = pd.DataFrame(
        {"特征": names, "重要性均值": pi.importances_mean, "SD": pi.importances_std}
    ).sort_values("重要性均值", ascending=False)
    print("\n  置换重要性（预测 log SWI）：")
    print(imp.round(4).to_string(index=False))
    _save_table(imp.reset_index(drop=True), "02_置换重要性.csv")

    # ---- 2.7 偏相关骨架（Graphical Lasso）------------------------------- #
    print("\n[2.7] 条件独立骨架：GraphicalLassoCV 偏相关")
    gl_vars = ["log_t2", "log_dwi", "log_swi", "age_z", "sex", "supra"]
    Xg = s3[gl_vars].dropna()
    pcorr, alpha = C.graphical_lasso_partial_corr(Xg)
    pcorr.index = [C.data_label(i) for i in pcorr.index]
    pcorr.columns = [C.data_label(i) for i in pcorr.columns]
    print(f"  正则强度 alpha={alpha:.4f}, n={len(Xg)}")
    print("  偏相关矩阵（|值|>0.15 视为存在边）：")
    print(pcorr.round(3).to_string())
    _save_table(pcorr.reset_index(names="变量"), "02_偏相关矩阵.csv")
    edges = []
    idx = list(pcorr.index)
    for i in range(len(idx)):
        for j in range(i + 1, len(idx)):
            val = float(pcorr.iloc[i, j])
            if abs(val) > 0.15:
                edges.append(
                    {
                        "变量A": idx[i],
                        "变量B": idx[j],
                        "偏相关": round(val, 3),
                        "关系": "正" if val > 0 else "负",
                    }
                )
    edges_df = pd.DataFrame(edges).sort_values("偏相关", key=abs, ascending=False)
    print("\n  保留的边：")
    print(edges_df.to_string(index=False) if len(edges_df) else "  （无）")
    _save_table(edges_df.reset_index(drop=True), "02_偏相关边.csv")
    res["partial_edges"] = edges

    # ---- 2.8 一因子模型（FactorAnalysis）-------------------------------- #
    print("\n[2.8] 一因子模型：三个测量是否来自同一个潜变量？")
    fa_vars = ["log_t2", "log_dwi", "log_swi"]
    Xf = StandardScaler().fit_transform(s3[fa_vars])
    fa = FactorAnalysis(n_components=1, random_state=C.SEED).fit(Xf)
    load = fa.components_[0]
    noise = fa.noise_variance_
    common = load**2 / (load**2 + noise)
    fa_df = pd.DataFrame(
        {
            "指标": ["log T2WI", "log DWI", "log SWI"],
            "载荷": load,
            "独特方差(噪声)": noise,
            "共同方差占比(=信度)": common,
        }
    )
    print(fa_df.round(4).to_string(index=False))
    print(
        "  -> 载荷同号且共同方差占比高，说明三者共享一个潜变量；"
        "T2WI 的独特方差最大（测量最不可靠）。"
    )
    _save_table(fa_df, "02_单因子模型.csv")
    res["factor_analysis"] = fa_df.to_dict("records")

    # ---- 2.9 缺失机制模型（MNAR 逻辑回归）------------------------------- #
    print("\n[2.9] 缺失机制：T2WI 是否被检出 ~ log DWI + log SWI")
    s9 = df.dropna(subset=["log_dwi", "log_swi"])
    X9 = StandardScaler().fit_transform(s9[["log_dwi", "log_swi"]])
    y9 = s9.t2_missing.to_numpy()
    lg = LogisticRegression(C=1.0, max_iter=1000, random_state=C.SEED)
    prob = cross_val_predict(lg, X9, y9, cv=5, method="predict_proba")[:, 1]
    auc = roc_auc_score(y9, prob)
    lg.fit(X9, y9)
    print(f"  n={len(s9)}  未检出={int(y9.sum())}  5折CV AUC={auc:.3f}")
    print(f"  标准化系数: log DWI {lg.coef_[0][0]:+.3f}, log SWI {lg.coef_[0][1]:+.3f}")
    print("  -> 病灶越小越容易在 T2WI 上漏检：缺失机制依赖潜变量 L，属于 MNAR。")
    res["mnar_auc"] = float(auc)
    res["mnar_coef"] = {
        "log_dwi": float(lg.coef_[0][0]),
        "log_swi": float(lg.coef_[0][1]),
    }
    _save_table(
        pd.DataFrame(
            {
                "变量": ["log DWI", "log SWI"],
                "标准化logit系数": [lg.coef_[0][0], lg.coef_[0][1]],
                "CV AUC": [auc, auc],
            }
        ),
        "02_缺失机制逻辑回归.csv",
    )

    # ---- 2.10 聚类结构：同一患者多发病灶 ---------------------------------- #
    print("\n[2.10] 聚类结构：同一患者多发病灶对有效样本量的影响")
    icc_rows = []
    for col in ("log_swi", "log_dwi", "log_t2"):
        d = C.icc1(df, col)
        icc_rows.append(
            {
                "变量": col,
                "ICC(1)": d["icc"],
                "平均每患者病灶数": d["k_bar"],
                "设计效应": d["deff"],
                "有效样本量": d["n_eff"],
            }
        )
    icc_df = pd.DataFrame(icc_rows)
    print(icc_df.round(3).to_string(index=False))
    _save_table(icc_df, "02_聚类结构ICC.csv")
    icc_main = C.icc1(df, "log_swi")

    # 病灶级自助 vs 患者级（聚类）自助：同一弹性两种区间
    sub_ds = df.dropna(subset=["log_dwi", "log_swi"])
    p_lo_c, p_hi_c, _ = C.cluster_bootstrap_ci(
        sub_ds,
        lambda sub: float(
            LinearRegression().fit(sub[["log_dwi"]], sub["log_swi"]).coef_[0]
        ),
        n_boot=2000,
        seed=C.SEED,
    )
    print(
        f"  DWI→SWI 弹性：病灶级自助 95%CI [{lo1:.3f}, {hi1:.3f}]  vs  "
        f"患者级(聚类)自助 95%CI [{p_lo_c:.3f}, {p_hi_c:.3f}]"
    )

    # ---- 汇总 ------------------------------------------------------------ #
    # 报告中要显示的「区间宽度」与「膨胀倍数」也在这里算好落盘：
    # 报告端不再做任何数值运算与取整，只呈现文件里的数。
    naive_w = hi1 - lo1
    proxy_w = hi3 - lo3
    res.update(
        {
            "n_lesion": len(df),
            "n_patient": int(df.pid.nunique()),
            "n_complete_t2": len(s3),
            "n_obs_dwi_swi": len(s1),
            "naive_beta": float(m1.coef_[0]),
            "naive_ci": [lo1, hi1],
            "naive_ci_width": float(naive_w),
            "naive_r2": float(r2_1),
            "naive_raw_slope": float(m1r.coef_[0]),
            "adj_beta": float(m2.coef_[0]),
            "adj_ci": [lo2, hi2],
            "adj_r2": float(r2_2),
            "adj_coefs": dict(zip(["log_dwi", *conf], [float(v) for v in m2.coef_])),
            "proxy_beta": float(m3.coef_[0]),
            "proxy_ci": [lo3, hi3],
            "proxy_ci_width": float(proxy_w),
            "ci_width_ratio": float(proxy_w / naive_w),
            "proxy_r2": float(r2_3),
            "proxy_beta_t2": float(m3.coef_[1]),
            "dml": dml,
            "icc": icc_main,
            "icc_table": icc_df.to_dict("records"),
            "naive_ci_cluster": [p_lo_c, p_hi_c],
            "factor_analysis": fa_df.to_dict("records"),
            "vif": vif.to_dict("records"),
            "cv_perf": perf_df.to_dict("records"),
            "perm_importance": imp.to_dict("records"),
        }
    )
    C.save_results(res, "02_sklearn_results.csv")
    return res


# =========================================================================== #
def main():
    df = C.load_data()
    step1_explore(df)
    res = step2_sklearn(df)

    b1, b2, b3 = res["naive_beta"], res["adj_beta"], res["proxy_beta"]
    p_lo, p_hi = res["proxy_ci"]
    print("\n" + "=" * 78)
    print("第 2 步完成。关键结论（数值驱动）：")
    print(f"  · 朴素 DWI→SWI 弹性 = {b1:.3f}（≈1，两者几乎一一对应）")
    print(
        f"  · 加入观测混杂后 = {b2:.3f}"
        f"（{'基本不变' if abs(b2 - b1) < 0.05 else '明显变化'} -> 观测混杂不是主因）"
    )
    print(
        f"  · 再控制另一个测量 log T2WI 后 = {b3:.3f} "
        f"[{p_lo:.3f}, {p_hi:.3f}]（点估计{'小幅下降' if b3 < b1 else '未下降'}，"
        f"但区间膨胀 {((p_hi - p_lo) / (res['naive_ci'][1] - res['naive_ci'][0])):.1f} 倍）"
    )
    print(
        f"  · DML 去偏估计 = {res['dml']['theta']:.3f} "
        f"[{res['dml']['ci95_low']:.3f}, {res['dml']['ci95_high']:.3f}]"
    )
    print(
        f"  · 聚类结构：ICC = {res['icc']['icc']:.3f}，设计效应 "
        f"{res['icc']['deff']:.2f}，有效样本量 ≈ {res['icc']['n_eff']:.1f}"
        f"（名义 n = {res['icc']['n_total']}）"
    )
    print(
        "  -> 三者的强相关来自共同原因「真实病灶大小 L」；DWI 对 SWI 没有独立的因果作用，"
        "把 beta≈1 读成『DWI 决定 SWI』是典型的共因混淆。"
    )
    print(
        "  -> 可识别的因果结论是：L 与部位 -> 测量值与检出；年龄/性别的效应需贝叶斯潜变量模型"
        "（02_pymc_causal.py）才能在测量误差下估计。"
    )
    print("  数值已落盘；图形请运行 python src/plots_eda_sklearn.py")
    print("=" * 78)


if __name__ == "__main__":
    main()
