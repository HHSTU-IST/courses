from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "images"
DAT = ROOT / "data"
IMG.mkdir(parents=True, exist_ok=True)
DAT.mkdir(parents=True, exist_ok=True)
DEFAULT_XLSX = DAT / "cav_dwi_swi.xlsx"

SEED = 42

# --------------------------------------------------------------------------- #
# 医学含义假设（报告中引用）
# --------------------------------------------------------------------------- #
MEDICAL_NOTES = {
    "性别": "生物学性别，可能与病灶发生部位/大小的基线差异有关，作为外生协变量。",
    "年龄（岁）": "患者年龄。假设随年龄增长病灶（尤其含铁血黄素沉积）累积，可能是病灶大小的原因。",
    "部位": "病灶解剖部位（额/颞/顶/枕叶、小脑、脑桥）。幕上 vs 幕下影响磁敏感伪影与"
    "可测量性，是「部位 -> 测量值」与「部位 -> 真实大小」的共同原因（混杂/前门变量）。",
    "T2WI (mm)": "T2 加权像测得的最大径。含铁血黄素环呈低信号，但对小病灶灵敏度最低，"
    "易漏检（数据中大量 '-')，且部分容积效应导致系统性低估计（衰减）。",
    "DWI (mm)": "扩散加权像测得的最大径。对细胞密度/含铁血黄素敏感，小病灶检出率优于 T2WI。",
    "SWI (mm)": "磁敏感加权像测得的最大径。对含铁血黄素/钙化最敏感，检出率最高（本数据无缺失），"
    "通常测量的病灶范围最大，被本文设为「潜变量真值尺度」的锚点。",
}

# --------------------------------------------------------------------------- #
# 绘图
# --------------------------------------------------------------------------- #
_CJK_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "WenQuanYi Zen Hei",
    "Arial Unicode MS",
    "DengXian",
]
_CJK_FONT: str | None = None


def setup_matplotlib() -> str | None:
    """配置中文字体；若系统无 CJK 字体则返回 None（调用方应退回英文标签）。"""
    global _CJK_FONT
    matplotlib.use("Agg")
    try:
        from matplotlib import font_manager

        available = {f.name for f in font_manager.fontManager.ttflist}
    except (ImportError, AttributeError, OSError, ValueError, TypeError):
        # 字体表可能因损坏的字体文件 / 受限的字体目录而无法枚举；
        # 此时退回英文标签即可，不应让绘图配置中断整个分析流程。
        available = set()
    _CJK_FONT = next((c for c in _CJK_CANDIDATES if c in available), None)

    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 150,
            "savefig.bbox": "tight",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 9.5,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )
    if _CJK_FONT:
        plt.rcParams["font.sans-serif"] = [_CJK_FONT, *_CJK_CANDIDATES]
        plt.rcParams["axes.unicode_minus"] = False
    else:
        plt.rcParams["axes.unicode_minus"] = False
        print("[warn] 未找到中文字体，图中标签将使用英文。")
    return _CJK_FONT


def L(zh: str, en: str) -> str:
    """图内标签双语开关。"""
    return zh if _CJK_FONT else en


def boxplot(ax, data, tick_labels=None, **kwargs):
    """
    兼容不同 matplotlib 版本的箱线图封装。

    matplotlib 3.9 起 ``Axes.boxplot(labels=...)`` 被 ``tick_labels=`` 取代，
    3.11 起旧参数已彻底移除；此处两者都尝试。
    """
    if tick_labels is not None:
        try:
            return ax.boxplot(data, tick_labels=tick_labels, **kwargs)
        except TypeError:
            return ax.boxplot(data, labels=tick_labels, **kwargs)
    return ax.boxplot(data, **kwargs)


def savefig(fig, name: str) -> Path:
    path = IMG / name
    fig.savefig(path)
    plt.close(fig)
    print(f"  [figure] {path}")
    return path


# --------------------------------------------------------------------------- #
# 数据加载 / 清洗
# --------------------------------------------------------------------------- #
def _to_num(s: pd.Series) -> pd.Series:
    """把可能含 '-', '—', '－', 空串 的列转成 float，无效值 -> NaN。"""
    x = s
    if not pd.api.types.is_numeric_dtype(x):
        x = x.astype(str).str.strip()
        for ch in ("－", "—", "–", "ー"):
            x = x.str.replace(ch, "-", regex=False)
        x = x.str.replace(r"^[-—－\s]*$", "", regex=True)
        x = x.replace({"": None, "nan": None, "None": None, "NaN": None, "NA": None})
    return pd.to_numeric(x, errors="coerce")


_REGION_MAP = ("额叶", "颞叶", "顶叶", "枕叶", "小脑", "脑桥")
_SUPRA = {"额叶", "颞叶", "顶叶", "枕叶"}  # 幕上
_INFRA = {"小脑", "脑桥"}  # 幕下（后颅窝）


def load_data(path: str | Path = DEFAULT_XLSX, verbose: bool = True) -> pd.DataFrame:
    """
    读取并清洗数据。

    返回列
    ------
    pid        患者编号（由「序号」前向填充得到）
    sex        1=男, 0=女
    age        年龄（岁）
    loc        病灶部位原文（如「右侧顶叶」）
    region     解剖分区（额叶/颞叶/顶叶/枕叶/小脑/脑桥）
    supra      1=幕上, 0=幕下
    side       1=左, 0=右, -1=中线/未标注
    t2/dwi/swi 三个序列的最大径 (mm)，未检出 = NaN
    log_*      对应 log 值（仅观测到才非空）
    t2_missing/dwi_missing  是否未检出（1/0）
    """
    raw = pd.read_excel(path)
    df = pd.DataFrame(index=raw.index)

    # ---- 第 1 列：序号 -> 患者 id（Excel 合并单元格导致 NaN，前向填充）
    df["pid"] = raw.iloc[:, 0].ffill().astype("int64")

    # ---- 第 2 列：性别（Excel 合并单元格 -> 同一患者只在首行有值，须在患者内前向填充）
    sex_raw = raw.iloc[:, 1].astype(str).str.strip()
    df["sex"] = sex_raw.map({"男": 1, "女": 0})

    # ---- 第 3 列：年龄（同上，患者级变量，向病灶级展开）
    df["age"] = _to_num(raw.iloc[:, 2])

    # 患者级协变量向该患者的所有病灶展开；分组内 ffill/bfill，避免跨患者串值
    for col in ("sex", "age"):
        df[col] = df.groupby("pid", sort=False)[col].ffill()
        df[col] = df.groupby("pid", sort=False)[col].bfill()

    # ---- 第 4 列：部位（同患者内若缺失则用该患者其它病灶的部位补齐）
    loc = raw.iloc[:, 3].astype(str).str.strip().replace({"nan": None, "": None})
    df["loc"] = loc
    df["loc"] = df.groupby("pid")["loc"].transform(lambda s: s.ffill().bfill())

    def _region(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "未知"
        for r in _REGION_MAP:
            if r in str(v):
                return r
        return "未知"

    df["region"] = df["loc"].map(_region)
    df["supra"] = df["region"].map(
        lambda r: 1 if r in _SUPRA else (0 if r in _INFRA else np.nan)
    )

    def _side(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return -1
        s = str(v)
        if s.startswith("左"):
            return 1
        if s.startswith("右"):
            return 0
        return -1

    df["side"] = df["loc"].map(_side)

    # ---- 第 5~7 列：T2WI / DWI / SWI 最大径
    for name, pos in (("t2", 4), ("dwi", 5), ("swi", 6)):
        df[name] = _to_num(raw.iloc[:, pos])

    for name in ("t2", "dwi", "swi"):
        df[f"{name}_missing"] = df[name].isna().astype(int)
        with np.errstate(divide="ignore", invalid="ignore"):
            df[f"log_{name}"] = np.where(
                df[name].notna() & (df[name] > 0),
                np.log(df[name].clip(lower=1e-9)),
                np.nan,
            )

    df["n_lesion_patient"] = df.groupby("pid")["pid"].transform("size")

    if verbose:
        print(f"读入 {path}")
        print(f"  原始形状 {raw.shape}  ->  清洗后 {df.shape}")
        print(
            f"  患者数 {df['pid'].nunique()}，病灶数 {len(df)}，"
            f"单人最多病灶 {df['n_lesion_patient'].max()}"
        )
        print(
            f"  缺失：T2WI {df['t2_missing'].sum()} / DWI {df['dwi_missing'].sum()} "
            f"/ SWI {df['swi_missing'].sum()}"
        )
        print(
            f"  患者级协变量缺失：sex {int(df['sex'].isna().sum())} / "
            f"age {int(df['age'].isna().sum())}"
        )
    # 患者级协变量必须填满（否则说明 Excel 结构与预期不同）
    for col in ("sex", "age"):
        if df[col].isna().any():
            raise ValueError(f"{col} 仍存在缺失，请检查 Excel 合并单元格结构。")
    return df


# --------------------------------------------------------------------------- #
# 通用统计工具
# --------------------------------------------------------------------------- #
def bootstrap_ci(
    x: np.ndarray,
    y: np.ndarray | None = None,
    stat: str = "mean",
    n_boot: int = 4000,
    alpha: float = 0.05,
    seed: int = SEED,
) -> tuple[float, float]:
    """
    自助法置信区间。

    ``stat='mean'`` 只使用 ``x``；``stat='pearson'`` / ``'spearman'`` 需同时给出
    ``y``，否则抛 ``ValueError``（而不是在循环内部抛出难以定位的 ``TypeError``）。
    """
    if stat != "mean" and y is None:
        raise ValueError(f"stat={stat!r} 需要同时提供 y。")

    x_arr = np.asarray(x, dtype=float)
    y_arr = None if y is None else np.asarray(y, dtype=float)
    rng = np.random.default_rng(seed)
    n = len(x_arr)
    out = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        if stat == "mean":
            out[b] = np.mean(x_arr[idx])
            continue
        if y_arr is None:  # pragma: no cover - 前面已校验，此处仅用于类型收窄
            raise ValueError(f"stat={stat!r} 需要同时提供 y。")
        if stat == "pearson":
            out[b] = np.corrcoef(x_arr[idx], y_arr[idx])[0, 1]
        elif stat == "spearman":
            out[b] = pd.Series(x_arr[idx]).corr(
                pd.Series(y_arr[idx]), method="spearman"
            )
        else:  # pragma: no cover
            raise ValueError(stat)
    lo, hi = np.nanpercentile(out, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def cluster_bootstrap_ci(
    df: pd.DataFrame, stat_fn, n_boot: int = 4000, alpha: float = 0.05, seed: int = SEED
) -> tuple[float, float, np.ndarray]:
    """
    患者级（聚类）自助法置信区间。

    同一患者可有多发病灶，病灶级自助法会低估不确定性；此处重采样「患者」
    而非「病灶」，得到对组内相关稳健的区间。

    返回 (lo, hi, boot_dist)。
    """
    rng = np.random.default_rng(seed)
    pids = df["pid"].unique()
    groups = [df[df["pid"] == p] for p in pids]
    out: list[float] = []
    n_skipped = 0
    for _ in range(n_boot):
        pick = rng.integers(0, len(pids), len(pids))
        sub = pd.concat([groups[i] for i in pick], ignore_index=True)
        try:
            v = stat_fn(sub)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError):
            # 个别重采样样本可能退化（例如抽到的子集内取值全同，相关系数或
            # 回归系数未定义），跳过该样本即可，并在末尾汇报跳过比例。
            n_skipped += 1
            continue
        if v is not None and np.isfinite(v):
            out.append(float(v))
    if n_skipped:
        print(f"  [warn] 聚类自助法跳过 {n_skipped}/{n_boot} 个退化重采样样本。")
    arr = np.asarray(out)
    lo, hi = np.percentile(arr, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi), arr


def icc1(df: pd.DataFrame, value_col: str, group_col: str = "pid") -> dict:
    """
    单因素随机效应 ICC(1)：同一患者内病灶取值的组内相关。

    同时给出设计效应 deff = 1 + (k̄ - 1)·ICC 与有效样本量 n_eff = n / deff，
    用于说明「39 个病灶来自 28 位患者」时统计推断的自由度损失。
    """
    sub = df[[group_col, value_col]].dropna()
    n_total = len(sub)
    n_groups = int(sub[group_col].nunique())
    if n_groups < 2 or n_total <= n_groups:
        return {"icc": np.nan, "k_bar": np.nan, "deff": np.nan, "n_eff": np.nan}
    g = sub.groupby(group_col)[value_col]
    sizes = g.size()
    # 不平衡设计下的平均组大小
    k_bar = float((n_total - (sizes**2).sum() / n_total) / (n_groups - 1))
    grand = sub[value_col].mean()
    ssb = float((sizes * (g.mean() - grand) ** 2).sum())
    ssw = float(((sub[value_col] - sub[group_col].map(g.mean())) ** 2).sum())
    msb = ssb / (n_groups - 1)
    msw = ssw / (n_total - n_groups)
    denom = msb + (k_bar - 1) * msw
    icc = (msb - msw) / denom if denom > 0 else np.nan
    icc = float(np.clip(icc, -1.0, 1.0))
    deff = 1.0 + (k_bar - 1.0) * icc
    return {
        "icc": icc,
        "k_bar": k_bar,
        "msb": msb,
        "msw": msw,
        "deff": float(deff),
        "n_eff": float(n_total / deff) if deff > 0 else float(n_total),
        "n_total": n_total,
        "n_groups": n_groups,
    }


def mnar_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    T2WI「未检出」组 vs「检出」组在 DWI / SWI 上的 Mann-Whitney 检验。

    若未检出组显著更小，说明缺失概率依赖潜变量「真实病灶大小」，
    即缺失非随机（MNAR），单值插补会产生偏倚。
    """
    from scipy import stats as _st

    g1 = df.loc[df["t2_missing"] == 1, ["dwi", "swi"]].dropna()
    g0 = df.loc[df["t2_missing"] == 0, ["dwi", "swi"]].dropna()
    rows = []
    for col in ("dwi", "swi"):
        a, b = g1[col].to_numpy(), g0[col].to_numpy()
        if len(a) == 0 or len(b) == 0:
            continue
        u, p = _st.mannwhitneyu(a, b, alternative="two-sided")
        rows.append(
            {
                "变量": col,
                f"T2未检出(n={len(a)}) 中位数": float(np.median(a)),
                f"T2检出(n={len(b)}) 中位数": float(np.median(b)),
                "Mann-Whitney U": float(u),
                "p值": float(p),
            }
        )
    return pd.DataFrame(rows)


def vif_table(X: pd.DataFrame) -> pd.DataFrame:
    """方差膨胀因子（用 linregress 式 R² 计算，避免额外依赖）。"""
    from sklearn.linear_model import LinearRegression

    rows = []
    for col in X.columns:
        others = [c for c in X.columns if c != col]
        if not others:
            rows.append({"变量": col, "VIF": 1.0})
            continue
        m = LinearRegression().fit(X[others], X[col])
        r2 = m.score(X[others], X[col])
        rows.append(
            {
                "变量": col,
                "R2_对其他变量": r2,
                "VIF": np.inf if r2 >= 1 else 1.0 / (1.0 - r2),
            }
        )
    return pd.DataFrame(rows).sort_values("VIF", ascending=False, ignore_index=True)


def graphical_lasso_partial_corr(X: pd.DataFrame, alphas: int = 30):
    """GraphicalLassoCV -> 稀疏精度矩阵 -> 偏相关（条件独立骨架）。"""
    from sklearn.covariance import GraphicalLassoCV

    Z = (X - X.mean()) / X.std(ddof=0)
    model = GraphicalLassoCV(alphas=alphas, cv=5, max_iter=500).fit(Z.values)
    prec = model.precision_
    d = np.sqrt(np.diag(prec))
    pcorr = -prec / np.outer(d, d)
    np.fill_diagonal(pcorr, 1.0)
    return pd.DataFrame(pcorr, index=X.columns, columns=X.columns), float(model.alpha_)


def dml_partial_linear(
    X: pd.DataFrame,
    T: pd.Series,
    Y: pd.Series,
    n_splits: int = 5,
    n_repeats: int = 10,
    n_boot: int = 2000,
    seed: int = SEED,
) -> dict:
    """
    双重机器学习（Double/Debiased ML）估计部分线性模型 Y = theta*T + g(X) + e 的 theta。

    残差正交化 + 交叉拟合：用 Ridge 学习 E[Y|X]、E[T|X]，再对残差做无截距回归。
    以重复 K 折的分布给出稳定性，用自助法给出置信区间。
    """
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import KFold, cross_val_predict

    thetas = []
    for r in range(n_repeats):
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=seed + r)
        y_res = np.asarray(Y) - cross_val_predict(Ridge(alpha=1.0), X, Y, cv=kf)
        t_res = np.asarray(T) - cross_val_predict(Ridge(alpha=1.0), X, T, cv=kf)
        thetas.append(float(t_res @ y_res / (t_res @ t_res)))

    # 用最后一次交叉拟合的残差做自助法
    rng = np.random.default_rng(seed)
    n = len(y_res)
    boots = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        tb, yb = t_res[idx], y_res[idx]
        boots[b] = tb @ yb / (tb @ tb)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "theta": float(np.mean(thetas)),
        "theta_sd_across_repeats": float(np.std(thetas)),
        "ci95_low": float(lo),
        "ci95_high": float(hi),
        "n": int(n),
        "n_repeats": n_repeats,
        "n_splits": n_splits,
    }


# 报告显示精度：**取整只在落盘这一处发生**。报告（report.typ）不再做任何
# 数值格式化，只原样呈现 data/ 里的字符，因此「数据文件 = 报告所见」。
ROUND_DIGITS = 4

# 落盘时转成中文的布尔列（报告端不再做 True/False 映射）
BOOL_LABELS = {True: "是", False: "否"}


def _fmt_num(v: float) -> str:
    """数值列的文本形式：定点 ``digits`` 位、去掉无意义的尾零。

    ``39.0`` 写成 ``39``、``20.5000`` 写成 ``20.5``、``-0.0`` 写成 ``0``。
    不四舍五入到别处、也不对极小值开后门 —— 小于 ``10^-digits`` 的量就是 0。
    """
    s = f"{v:.{ROUND_DIGITS}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-", "-0") else s


def _fmt_mixed(v):
    """混杂列里的单个值：布尔转中文、浮点按显示规则改写，其余原样。"""
    if isinstance(v, bool):
        return BOOL_LABELS[v]
    if isinstance(v, float):
        return v if np.isnan(v) else _fmt_num(v)
    return v


def _fmt_frame(df: pd.DataFrame, digits: int = ROUND_DIGITS) -> pd.DataFrame:
    """把表整理成「报告可直接显示」的形式 —— 落盘前的唯一一道格式化。

    - 数值列：取整到 ``digits`` 位（同时写入 CSV 的文本形式由 :func:`_fmt_num` 决定）；
    - 布尔列：写成「是 / 否」；
    - ``object`` 混杂列（如频数表的「取值」列同时含 ``0.0`` 与「小脑」）：
      列内浮点无法被 ``float_format`` 覆盖，这里显式改写，避免漏出 ``0.0``。
    """
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == bool:
            out[col] = out[col].map(BOOL_LABELS)
        elif pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].round(digits)
        elif out[col].dtype == object:
            out[col] = out[col].map(_fmt_mixed)
    return out


_RESULT_HEADER = ("指标", "值")
_SEP = "/"


def _join(prefix: str, key: str) -> str:
    return f"{prefix}{_SEP}{key}" if prefix else str(key)


def _flatten_results(obj, prefix: str = "", out: dict | None = None) -> dict:
    """把结果字典压平成 ``{层级路径: 标量}``。"""
    if out is None:
        out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten_results(v, _join(prefix, k), out)
    elif isinstance(obj, (list, tuple)):
        items = list(obj)
        if not items:
            return out  # 空列表（如尚未产出的模型比较）没有内容可落
        if all(isinstance(x, dict) for x in items):
            return out  # 记录列表 -> 各自的表 CSV，不在这里重复一份
        if len(items) == 2 and all(
            isinstance(x, (int, float)) and not isinstance(x, bool) for x in items
        ):
            out[_join(prefix, "下")] = items[0]
            out[_join(prefix, "上")] = items[1]
        else:
            for i, v in enumerate(items):
                _flatten_results(v, _join(prefix, str(i)), out)
    else:
        out[prefix] = obj
    return out


def _fmt_scalar(v) -> str:
    """结果长表「值」列的文本形式 —— 与表 CSV 共用同一套显示规则。"""
    if isinstance(v, (bool, np.bool_)):  # np.bool_ 不是 bool 的子类，要单独列
        return BOOL_LABELS[bool(v)]
    if isinstance(v, (float, np.floating)):
        return _fmt_num(round(float(v), ROUND_DIGITS))
    if isinstance(v, (int, np.integer)):
        return str(int(v))
    return str(v)


def _parse_scalar(s: str) -> bool | int | float | str:
    """长表「值」列 -> Python 值（数值与布尔还原类型，其余留作字符串）。"""
    t = s.strip()
    if t in BOOL_LABELS.values():
        return t == BOOL_LABELS[True]
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        return t


def save_results(obj, name: str) -> Path:
    """结果字典 -> ``data/<name>``（两列长表「指标,值」）。

    与 :func:`save_table` 一样，数值在落盘这一处定型：调用处不必再 ``.round(4)``。
    """
    path = DAT / name
    flat = _flatten_results(obj)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(_RESULT_HEADER)
        for k, v in flat.items():
            w.writerow([k, _fmt_scalar(v)])
    print(f"  [result] {path}")
    return path


def load_results(name: str) -> dict:
    """读回 ``data/<name>`` 的结果长表，还原成嵌套字典（供绘图等脚本使用）。

    ``dtype=str`` 是必须的：整列一起读时 pandas 会把「值」列推断成 float，
    于是 ``39`` 变成 ``39.0``、``n=37`` 印成 ``n=37.0``。
    逐字符读回来再按 :func:`_parse_scalar` 还原类型，文本才不会走样。
    """
    rows = pd.read_csv(
        DAT / name, encoding="utf-8-sig", keep_default_na=False, dtype=str
    )
    out: dict = {}
    for key, raw in zip(rows[_RESULT_HEADER[0]], rows[_RESULT_HEADER[1]]):
        parts = str(key).split(_SEP)
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = _parse_scalar(raw)
    return out


def save_table(df: pd.DataFrame, name: str, index: bool = False) -> Path:
    """数值表 -> ``data/<name>``（带 BOM，便于 Excel 直接打开）。

    数值先经 :func:`_fmt_frame` 统一整理（取整、布尔转中文、混杂列清洗），
    再按 :func:`_fmt_num` 写成报告可直接显示的文本 —— 调用处**不必**再写
    ``.round(4)``。
    """
    path = DAT / name
    _fmt_frame(df).to_csv(
        path, index=index, encoding="utf-8-sig", float_format=_fmt_num
    )
    print(f"  [table ] {path}")
    return path


def read_table(name: str, index_col: str | None = None) -> pd.DataFrame:
    """读取 ``data/<name>`` 数值表（兼容 :func:`save_table` 写出的 BOM）。"""
    return pd.read_csv(DAT / name, encoding="utf-8-sig", index_col=index_col)


# --------------------------------------------------------------------------- #
# 显示名
# --------------------------------------------------------------------------- #
# DATA_LABELS：写进数据文件（data/*.csv）的显示名。
#   **属数据契约，不要改** —— report.typ 的字段映射与这些名字对齐，
#   改名会让报告的表格文字跟着变（即使数值没变）。
DATA_LABELS: dict[str, str] = {
    "log_t2": "log T2WI",
    "log_dwi": "log DWI",
    "log_swi": "log SWI",
    "age": "Age",
    "sex": "Male",
    "supra": "Supratentorial",
    "side": "Left side",
}

# PLOT_LABELS：只影响图片里的文字，可自由增改。
#   比 DATA_LABELS 更全（例如补上数据文件里仍是原始键名的 age_z / left），
#   这样「让图上不再出现代码式变量名」不必去改数据文件。
PLOT_LABELS: dict[str, str] = {
    **DATA_LABELS,
    "age_z": "Age (z)",
    "left": "Left side",
    "region": "Region",
}


def data_label(name: str) -> str:
    """写进数据文件时使用的显示名（冻结，报告依赖它）。未登记的键原样返回。"""
    return DATA_LABELS.get(name, name)


def plot_label(name: str) -> str:
    """图内标签显示名（可自由调整，不影响数据文件与报告）。"""
    return PLOT_LABELS.get(name, name)


def analysis_frame(
    df: pd.DataFrame | None = None, *, verbose: bool = True
) -> pd.DataFrame:
    """加载数据并补上分析用派生列（``age_z`` / ``left``）。

    计算脚本与绘图脚本共用同一份定义，保证「绘图读到的数据」与
    「建模时用的数据」口径一致。
    """
    d = load_data(verbose=verbose) if df is None else df.copy()
    d["age_z"] = (d["age"] - d["age"].mean()) / d["age"].std(ddof=0)
    d["left"] = (d["side"] == 1).astype(int)
    return d
