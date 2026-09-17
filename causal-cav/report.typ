#set document(title: "DWI / SWI 颅内海绵状血管瘤因果关系分析：结果汇总报告")
#set text(font: ("Noto Serif SC",), size: 9.8pt, lang: "zh")
#set par(justify: true, leading: 0.7em, first-line-indent: (amount: 2em, all: true))
#set page(paper: "a4", margin: (x: 2.0cm, y: 2.2cm), numbering: "1")

#set heading(numbering: "1.1")

#show heading: set text(font: ("Noto Sans SC",), weight: "bold")
#show heading: set block(above: 1.2em, below: 0.55em)
#show heading.where(level: 1): set text(size: 13.5pt, fill: rgb("#1f4e79"))
#show heading.where(level: 2): set text(size: 11.3pt, fill: rgb("#2c6fb5"))
#show heading.where(level: 3): set text(size: 10.2pt, fill: rgb("#3d6f9e"))

// 正文引用节号时写作「第 @sec-xxx 节」「见 @sec-xxx」，编号随标题自动更新。
// Typst 默认会在编号前加「小节 / Section」这类补语，这里统一去掉，只留编号本身。
#show ref: set ref(supplement: none)

#show figure.where(kind: image): set figure(numbering: none)

#let table-three-line(stroke-color, head: auto) = {
  let head-rule = if head == auto { stroke-color } else { head }
  (x, y) => (
    top: if y == 0 { stroke-color } else if y == 1 { head-rule } else { 0pt },
    bottom: stroke-color,
  )
}


#show table: set table(
  inset: 4.5pt,
  stroke: table-three-line(0.7pt + luma(30), head: 0.35pt + luma(30)),
)
#show table: set text(size: 8.9pt)

// =========================================================================== //
// 数据读取工具
// =========================================================================== //
#let field-label = (
  // 尺寸变量
  "log_t2": "log T2WI",
  "log_dwi": "log DWI",
  "log_swi": "log SWI",
  "t2": "T2WI 最大径",
  "dwi": "DWI 最大径",
  "swi": "SWI 最大径",
  // 人口学与解剖协变量
  "age": "年龄",
  "age_z": "年龄（z 分）",
  "sex": "性别（男 = 1）",
  "supra": "幕上（幕上 = 1）",
  "Male": "男性",
  "Supratentorial": "幕上",
  "left": "左侧（左 = 1）",
  "side": "左右侧",
  "loc": "位置（原始记载）",
  "region": "解剖分区",
  "pid": "患者编号",
  "n_lesion_patient": "同患者病灶数",
  // 未检出标记
  "t2_missing": "T2WI 未检出标记",
  "dwi_missing": "DWI 未检出标记",
  "swi_missing": "SWI 未检出标记",
  // 正则化方法
  "LassoCV": "L1 正则化（Lasso）",
  "RidgeCV": "L2 正则化（Ridge）",
  // 表头
  "列名": "变量",
  "非空": "非缺失数",
  "缺失": "缺失数",
  "缺失率%": "缺失率（%）",
  "取值数": "不同取值数",
  "后验SD": "后验标准差",
  "ESS_bulk": "有效样本量（最小）",
  "最小 ESS_bulk": "有效样本量（最小）",
  "最小 ESS_tail": "尾部有效样本量（最小）",
  // 描述统计表头
  "count": "例数",
  "mean": "均值",
  "std": "标准差",
  "SD": "标准差",
  "min": "最小值",
  "25%": "25% 分位",
  "50%": "中位数",
  "75%": "75% 分位",
  "max": "最大值",
  "skew": "偏度",
  "CV%": "变异系数（%）",
  // 频数表里的变量名
  "性别(1男/0女)": "性别（男 = 1）",
  "幕上1/幕下0": "幕上（幕上 = 1）",
  "左1/右0/中线-1": "左右侧（左 = 1，中线 = −1）",
  // 贝叶斯模型参数
  "a_male": "性别（男）效应",
  "a_age": "年龄效应（每 1 岁）",
  "lam_d": "DWI 载荷",
  "lam_t": "T2WI 载荷",
  "sd[0]": "SWI 测量残差 SD",
  "sd[1]": "DWI 测量残差 SD",
  "sd[2]": "T2WI 测量残差 SD",
  "c0": "检出方程截距",
  "c1": "检出方程斜率",
  "tau_loc": "部位效应尺度 τ",
  "eff_age_10y": "年龄效应（每 +10 岁，倍数）",
  "eff_male": "男性效应（倍数）",
  "p_detect_Lm1": "检出概率（小病灶）",
  "p_detect_L0": "检出概率（中等病灶）",
  "p_detect_Lp1": "检出概率（大病灶）",
)

// 单元格显示名：命中映射表就换成可读文字，否则原样显示
#let rl(c) = if c in field-label { field-label.at(c) } else { c }

#let minus(s) = if s.starts-with("-") { "−" + s.slice(1) } else { s }

// 表 CSV -> 字典数组（首行是表头）。正文里引用「某张表的某一格」时用它，
// 使引用与那张表的正文渲染读的是同一份文件，不存在第二个来源。
#let dicts(path) = {
  let rows = csv(path)
  let head = rows.at(0)
  rows.slice(1).map(r => head.zip(r).map(p => (p.at(0), minus(p.at(1)))).to-dict())
}

// 结果长表 -> 嵌套字典。指标列是层级路径（dml/theta、ppc/观测均值），
// 两元组（置信区间）落成 <键>/下 与 <键>/上 两行。
// 分隔符用 `/` 而不是 `.` —— 有的键名自带点（model_C_delta.p_rope_0.1）。
#let res(path) = {
  let rows = csv(path).slice(1)
  let keys = rows.map(r => r.at(0))
  let tree(prefix) = {
    let head = if prefix == "" { "" } else { prefix + "/" }
    keys
      .filter(k => k.starts-with(head) and k.len() > head.len())
      .map(k => k.slice(head.len()).split("/").at(0))
      .dedup()
      .map(c => (
        c,
        {
          let full = head + c
          if full in keys { minus(rows.find(r => r.at(0) == full).at(1)) } else { tree(full) }
        },
      ))
      .to-dict()
  }
  tree("")
}

// 两份结果长表
#let r1 = res("data/02_sklearn_results.csv")
#let r3 = res("data/03_pymc_results.csv")

// 正文里会引用的那几张表的取值源（每个都是一行一条记录）
#let vif = dicts("data/02_VIF.csv")
#let cvp = dicts("data/02_CV性能.csv")
#let fct = dicts("data/02_单因子模型.csv")
#let iccs = dicts("data/02_聚类结构ICC.csv")
#let perm = dicts("data/02_置换重要性.csv")
#let mpar = dicts("data/03_pymc_模型A参数.csv")
#let reg = dicts("data/03_pymc_部位效应.csv")
#let diag = dicts("data/03_pymc_收敛诊断.csv")

// 区间文本，如 [0.9487, 1.0246]。参数有两种来源：结果长表里成对的
// 「<键>.下 / <键>.上」（读回来是字典），或正文里显式写出的两个标量（数组）。
#let ci(v) = {
  let pair = if type(v) == dictionary { (v.at("下"), v.at("上")) } else { (v.at(0), v.at(1)) }
  "[" + str(pair.at(0)) + ", " + str(pair.at(1)) + "]"
}

// 模型 A 后验查表
#let pa(name) = mpar.find(p => p.at("参数") == name)
#let praw(name) = pa(name).at("后验均值")
#let pv(name) = praw(name)
#let pl(name) = pa(name).at("95%HDI 下")
#let pu(name) = pa(name).at("95%HDI 上")

// =========================================================================== //
// 封面区
// =========================================================================== //
#align(center)[
  #v(0.4cm)
  #text(size: 17pt, weight: "bold", font: ("Noto Sans SC",), fill: rgb("#1f4e79"))[
    DWI / SWI 在颅内海绵状血管瘤诊断中的因果关系分析 \
  ]
  #v(0.15cm)
  #text(size: 11pt, fill: luma(80))[结果汇总报告：回归与贝叶斯潜变量双路径建模]
  #v(0.5cm)
]

#align(center)[
  #set text(size: 9pt, fill: luma(90))
  #block(stroke: 0.5pt + luma(190), inset: 10pt, radius: 3pt, width: 100%)[
    #set par(first-line-indent: 0em)
    #set align(left)
    #grid(
      columns: (auto, 1fr),
      row-gutter: 4pt,
      column-gutter: 8pt,
      [*样本*], [#r1.n_lesion 个病灶 / #r1.n_patient 位患者],
      [*变量*], [性别、年龄、部位、T2WI、DWI、SWI],
      [*方法*], [回归与双重机器学习去偏估计；贝叶斯潜变量测量模型 + 缺失机制选择方程],
      [*核心结论*],
      [T2WI、DWI、SWI 三个序列测的是同一个"真实病灶大小"，只是各自多带了一点测量误差；DWI 对 SWI 没有可检出的直接影响],
    )
  ]
]

#v(0.3cm)

#outline(title: [目录], depth: 2, indent: auto)

#pagebreak()

= 研究问题与数据 <sec-data>

== 问题设定 <sec-problem>

本报告回答两组问题：

+ *关联层面*：性别、年龄、部位与三个序列测量之中，哪些能预测其余？T2WI、DWI、SWI 三个测量之间近乎一一对应的强相关（弹性约为 1）究竟意味着什么？
+ *因果层面*：在控制可观测协变量、并显式建模测量误差与缺失机制之后，DWI 对 SWI 是否还存在*独立的直接因果效应*？年龄、性别、病灶部位是否影响真实病灶大小？

六项变量为：性别、年龄、部位、T2WI、DWI、SWI。前三者是患者或病灶层面的属性，后三者是同一病灶在三个脉冲序列上测得的最大径（mm）。

== 数据结构与变量类型 <sec-variables>

同一患者的多个病灶记录中，患者级信息（性别、年龄）只在首行给出，其余病灶行留空；尺寸字段的缺失表示该序列*未检出*该病灶，而不是录入错误，因此按患者把患者级信息补齐到每条病灶记录，并把该缺失标记理解为"未检出"。

#figure(
  {
    let rows = csv("data/01_变量概览.csv").map(r => r.slice(0, 1) + r.slice(2))
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [变量与缺失概览（清洗后）。三序列中仅 SWI 无缺失，T2WI 缺失最严重。],
)

从表可直接读出缺失量：T2WI 缺失 20.5%、DWI 5.1%、SWI 为 0。由于 T2WI 缺失，三序列齐全的样本降到 #r1.n_complete_t2 个，可分析样本减少约 21%，这是一切"完整病例分析"的共同约束。

== 分布与频数 <sec-distribution>

#figure(
  {
    show table: set text(size: 8.2pt)
    let rows = csv("data/01_连续变量描述.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [连续变量描述统计（尺寸单位 mm，年龄单位岁）。三个尺寸变量右偏严重，均值远大于中位数。],
)

三序列的偏度都在 2.2 至 2.4 之间、变异系数约 85%，均值被少数大病灶拉高（最大 41 mm）。这正是后续对尺寸取对数（log(mm)）的原因：对数尺度上系数可直接读作*弹性*。

#figure(
  {
    let rows = csv("data/01_分类变量频数.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [分类变量频数。性别基本均衡；部位以枕叶最多、小脑最少，亚组仅 5 至 8 例。],
)

== 缺失模式 <sec-missingness>

#figure(
  image("images/fig01_missingness.png", width: 100%),
  caption: [(a) 各序列未检出例数；(b) DWI 与 SWI 散点——未检出的点全部集中在左下角，即"缺失"与"病灶小"直接绑定，而不是随机散落。],
)

#figure(
  image("images/fig02_distributions.png", width: 100%),
  caption: [(a) 年龄分布（近对称）；(b) 三序列测量分布（右偏）；(c) SWI 按解剖分区的分布，各亚组样本量小、区间重叠严重。],
)

== 医学含义假设 <sec-clinical>

以下假设决定了后续所有模型的变量角色，均属*待检验*的领域假设而非既定事实：

- *性别*：生物学性别。作为外生协变量，假设其可能与病灶基线大小或好发部位有关。
- *年龄*：患者年龄。假设随年龄增长含铁血黄素沉积累积，因而可能是病灶大小的原因。
- *部位*：额、颞、顶、枕叶与小脑、脑桥。幕上与幕下影响磁敏感伪影与可测量性，因此它同时影响"真实大小"与"测量误差"，是典型的共同原因（混杂 / 前门变量）。
- *T2WI*：含铁血黄素环呈低信号，但小病灶灵敏度最低，易漏检，且部分容积效应导致系统性低估。
- *DWI*：对细胞密度与含铁血黄素敏感，小病灶检出率优于 T2WI。
- *SWI*：对含铁血黄素与钙化最敏感，检出率最高（无缺失），通常测得范围最大，因此被设为潜变量尺度的锚点。

== 预处理决策 <sec-preprocessing>

- 患者标识：按病例序号归组，得到 #r1.n_patient 位患者 / #r1.n_lesion 个病灶。
- T2WI、DWI 中未检出的记录记为缺失值，语义是"该序列未检出该病灶"。
- 部位缺失 1 例（患者 18 的第 2 个病灶）用同患者其它病灶的部位补齐；其余不做插补。
- 三个尺寸变量取对数（log T2WI、log DWI、log SWI），系数解释为弹性。
- 性别编码 男 1 / 女 0；派生出幕上（1）与左右侧（左 1 / 右 0 / 中线 -1）。
- *不做单值插补*：T2WI 缺失与病灶大小强相关（下一节验证为 MNAR），插补会引入偏倚；因此在建模阶段改用显式的缺失机制模型处理。

= 探索性分析 <sec-eda>

== 三序列之间的相关 <sec-correlation>

以各序列配对可得的样本计算 Pearson 相关（对数尺度），置信区间为 2000 次自助法：

#figure(
  {
    let rows = csv("data/01_尺寸变量配对相关.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [配对相关。三者相关均在 0.99 上下，区间极窄。],
)

#figure(
  {
    let rows = csv("data/01_Pearson相关.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [Pearson 相关矩阵（对数尺度尺寸）。左上 3×3 区块（三序列之间）为 0.99 量级，与协变量的相关都很弱。],
)

#figure(
  {
    let rows = csv("data/01_Spearman相关.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [Spearman 相关矩阵。与 Pearson 数值几乎相同，说明这种相关不是被极端值造成的，而是整体单调对齐。],
)

#figure(
  image("images/fig03_correlation.png", width: 90%),
  caption: [Pearson 与 Spearman 相关热图。三序列之间近似常数相关（约 0.99），而它们与年龄、性别、幕上的相关都在 0.34 以下。],
)

== 缺失机制：MNAR 检验 <sec-mnar>

若"未检出"只是随机的技术噪声，未检出组与检出组的病灶大小分布应当相近，但实际结果相反：

#figure(
  {
    let rows = csv("data/01_缺失机制检验.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [T2WI 未检出组在 DWI 与 SWI 上都显著更小。注意 n=6 而非 8：缺失的 8 个病灶中有 2 个同时缺 DWI，被剔除出配对检验。],
)

#figure(
  {
    let rows = csv("data/02_缺失机制逻辑回归.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [用 log DWI 与 log SWI 预测量"T2WI 是否未检出"的逻辑回归。两个系数都为负，与"病灶越小越容易未检出"一致。],
)

逻辑回归的 5 折交叉验证 *AUC = #(r1.mnar_auc)*，标准化 logit 系数为 log DWI #(r1.mnar_coef.at("log_dwi"))、log SWI #(r1.mnar_coef.at("log_swi"))：病灶越小，越可能被记录为"未检出"。

#figure(
  image("images/fig08_mnar.png", width: 90%),
  caption: [(a) T2WI 缺失组的病灶显著更小；(b) 未检出的逻辑回归系数，交叉验证 AUC 达 0.95。],
)

#align(center)[
  #block(
    width: 100%,
    inset: 9pt,
    radius: 3pt,
    fill: rgb("#fdf4ef"),
    stroke: (left: 2.5pt + rgb("#b5542c")),
  )[
    #set par(first-line-indent: 0em)
    *结论：T2WI 缺失属于 MNAR（非随机缺失）。* 缺失概率依赖潜变量"真实病灶大小"本身，因此单值插补、或用完整病例直接代表全体都会引入偏倚，而后续贝叶斯模型显式写出这一检出选择方程。
  ]
]

= 回归与去偏估计 <sec-regression>

== DWI 对 SWI 的系数随设定变化 <sec-coefficient>

把三序列当作三个独立变量，用最小二乘（对数尺度）逐一加入控制。四种设定下的结果如下：

#figure(
  {
    show table: set text(size: 9.8pt)
    table(
      columns: 5,
      align: (auto, center, center, center, center),
      table.header([*模型*], [*n*], [*系数*], [*95%CI*], [*R²*]),
      [M1 仅 DWI], [#(r1.n_obs_dwi_swi)], [#(r1.naive_beta)], [#ci(r1.naive_ci)], [#(r1.naive_r2)],
      [M2 + 观测混杂], [#(r1.n_obs_dwi_swi)], [#(r1.adj_beta)], [#ci(r1.adj_ci)], [#(r1.adj_r2)],
      [M3 + log T2WI], [#(r1.n_complete_t2)], [#(r1.proxy_beta)], [#ci(r1.proxy_ci)], [#(r1.proxy_r2)],
      [M4 双重机器学习（交叉拟合）], [#(r1.dml.n)], [#(r1.dml.theta)], [#ci((r1.dml.ci95_low, r1.dml.ci95_high))], [—],
    )
  },
  caption: [DWI 对 SWI 的弹性在不同设定下的变化。M2 的观测混杂为年龄（z 分）、性别、幕上、左右侧；M3 在完整病例子集上估计，故 n 降为 #(r1.n_complete_t2)。],
)

M2 中观测混杂的系数全部接近 0（年龄 z 分#(r1.adj_coefs.at("age_z"))、性别 #(r1.adj_coefs.at("sex"))、幕上 #(r1.adj_coefs.at("supra"))、左侧 #(r1.adj_coefs.at("left"))），说明*观测到的*协变量几乎不解释这条关联；原始尺度上的斜率（mm/mm）为#(r1.naive_raw_slope)，同样接近 1。

M3 的表现是关键诊断：加入 log T2WI 后点估计并未下降（#(r1.naive_beta) 变为 #(r1.proxy_beta)），但置信区间宽度从 #(r1.naive_ci_width) 膨胀到#(r1.proxy_ci_width)（约 #(r1.ci_width_ratio) 倍），而新变量自身的系数仅 #(r1.proxy_beta_t2) 且接近 0。这种"点估计稳定、方差爆炸"的组合，是*共线代理变量互相争夺解释力*的特征，而不是"效应被解释掉"。

#figure(
  image("images/fig04_elasticity_compare.png", width: 80%),
  caption: [四个模型的系数与 95% 自助置信区间。M1 至 M3 的点估计都紧贴 1.0，但 M3 的区间比 M1 宽一个数量级。],
)

三种估计方式给出同一答案：

- 朴素弹性 #(r1.naive_beta) #ci(r1.naive_ci)；
- 双重机器学习（DML，5 折 × #(r1.dml.n_repeats) 次重复交叉拟合，残差正交化）theta = *#(r1.dml.theta)*#ci((r1.dml.ci95_low, r1.dml.ci95_high))，重复间标准差仅 #(r1.dml.theta_sd_across_repeats)；
- 患者级（聚类）自助区间 #ci(r1.naive_ci_cluster)，与病灶级 #ci(r1.naive_ci) 几乎相同。

#align(center)[
  #block(
    width: 100%,
    inset: 9pt,
    radius: 3pt,
    fill: rgb("#fdf4ef"),
    stroke: (left: 2.5pt + rgb("#b5542c")),
  )[
    #set par(first-line-indent: 0em)
    *数据质量提示（关于 @sec-collinearity 节的正则化系数表）。* 该分析把 SWI 的测量值同时用作解释变量与待预测的结果——在"预测 SWI"的模型里，SWI 自己也在自变量之列，构成直接的响应变量泄漏。后果有两点：该表中 SWI 的 VIF、以及"预测 SWI"的标准化系数都不能被解读为预测能力；本报告保留该表以反映原始分析结果，但请勿据此表下结论。
  ]
]

== 共线性 <sec-collinearity>

#figure(
  {
    let rows = csv("data/02_VIF.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [方差膨胀因子。三个尺寸变量的 VIF 全部远超 10，而三个协变量都在 2 以下。],
)

三序列的 VIF 都在 65 以上（log DWI 达 #(vif.at(0).at("VIF"))），意味着它们在信息上高度冗余；相反，年龄、性别、幕上的共线性可以忽略，这本身就提示：把它们当作三个独立解释变量回归没有意义。

#figure(
  {
    let rows = csv("data/02_正则化系数.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [标准化系数（预测 log SWI）。L1 正则化（Lasso）把协变量全部压为 0；但该表含上一节所述的响应变量泄漏，仅作参考。],
)

== 预测性能与置换重要性 <sec-performance>

#figure(
  {
    let rows = csv("data/02_CV性能.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [5 折 × 10 次重复交叉验证的 R²。仅用 log DWI 一个变量就已达到 0.985。],
)

#figure(
  {
    let rows = csv("data/02_置换重要性.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [随机森林的置换重要性（60 次重复，以 R² 为评分）。重要性几乎完全集中在两个尺寸变量上。],
)

#figure(
  image("images/fig06_importance.png", width: 100%),
  caption: [置换重要性。log DWI 与 log T2WI 几乎平分全部重要性，其余变量可忽略；随机森林的交叉验证 R² 反而低于单变量线性模型。],
)

随机森林在交叉验证中*不如*单变量线性回归（#(cvp.at(3).at("CV R2 均值"))对 #(cvp.at(0).at("CV R2 均值"))）。这不是模型不够强，而是数据结构的直接后果：关系本身就是近乎确定性的单调线性关系，增加容量只会增加方差。

== 条件独立骨架（偏相关） <sec-partial-corr>

用图 Lasso（Graphical Lasso）估计稀疏精度矩阵，再转成偏相关（即在*控制其余全部变量*之后的剩余相关）。完整矩阵与只保留 |偏相关| 大于 0.15 的边如下：

#figure(
  {
    // 覆盖表格字号：普通 set text 会被开头的 show 规则盖住，须同样写成 show
    show table: set text(size: 8.6pt)
    let rows = csv("data/02_偏相关矩阵.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [偏相关矩阵。控制其余变量后，三序列之间仍保留明显偏相关。],
)

#figure(
  {
    let rows = csv("data/02_偏相关边.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [保留的偏相关边。除三序列互相连接外，还出现年龄与性别、性别与部位、年龄与部位的关联。],
)

#figure(
  image("images/fig05_partial_corr.png", width: 100%),
  caption: [偏相关热图与保留边。尺寸变量之间的偏相关达 0.35 至 0.63，说明它们共享未被观测的共同来源；年龄与性别之间的 -0.375 是样本内的人群特征。],
)

== 单因子模型 <sec-factor>

对 log T2WI、log DWI、log SWI 拟合单因子模型（因子分析，1 个公因子）：

#figure(
  {
    let rows = csv("data/02_单因子模型.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [单因子解。三者的载荷均在 0.99 以上，独特方差不足 2%。],
)

#figure(
  image("images/fig07_factor_analysis.png", width: 80%),
  caption: [(a) 三个指标在同一条公因子上的载荷都接近 1；(b) 方差分解显示几乎所有方差都是共同方差，独特（噪声）方差极小。],
)

三者的共同方差占比都超过 98%，也就是说它们在测量同一个东西。但必须立刻补充第 @sec-bayes 节的关键限定：*这一单因子解在本设计中是恰好识别的，因而"拟合良好"不构成证据*。

== 聚类结构 <sec-clustering>

#r1.n_lesion 个病灶来自 #r1.n_patient 位患者，同一患者内可能相关，需要用患者级统计量检查：

#figure(
  {
    let rows = csv("data/02_聚类结构ICC.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [单因素随机效应 ICC(1) 与设计效应。DWI 与 SWI 的组内相关接近 0 或为负。],
)

DWI 与 SWI 的 ICC(1) 分别为 #(iccs.at(1).at("ICC(1)")) 与#(iccs.at(0).at("ICC(1)"))，设计效应 #(iccs.at(0).at("设计效应"))，有效样本量约 #(iccs.at(0).at("有效样本量"))（名义 #r1.n_lesion）。患者级自助区间 #ci(r1.naive_ci_cluster) 与病灶级#ci(r1.naive_ci) 几乎完全一致，说明聚类结构没有实质影响结论，无需引入多层模型。

= 贝叶斯潜变量测量模型 <sec-bayes>

第 @sec-regression 节从相关结构、预测表现与去偏关联出发得出结论，本节改从生成过程出发，重新估计同一批数据。目的不是另起一套互相比对的结论，而是检验那些规律在一个含测量误差与缺失机制的完整模型下是否依然成立，以及结构上还能多给出什么。

== 模型结构 <sec-model-structure>

#figure(
  image("images/fig09_pymc_dag.drawio.png", width: 60%),
  caption: [图中蓝色框为外生协变量，粉色框为潜变量 L，绿色框为三个序列的测量值，紫色框为检出指示，红色虚线是模型 C 额外允许的 DWI 直接通路。],
)

模型把三个序列明确写成同一潜变量的三个带噪测量，并把 SWI 的载荷锚定为 1（噪声最小、无缺失，作为尺度基准）：

$
  "log SWI" = nu_1 + L + epsilon_1, quad "log DWI" = nu_2 + "lam"_d L + epsilon_2, quad "log T2WI" = nu_3 + "lam"_t L + epsilon_3
$

同时显式写出 MNAR 检出方程：$P("T2WI 检出") = "sigmoid"(c_0 + c_1 L)$，并让 T2WI 的测量似然只在"检出"子集上成立；DWI 的 2 个缺失按 MAR 由模型插补。由于 L 被显式建模，条件化 L 之后"是否被检出"是外生的，用检出子集拟合 T2WI 方程不会引入偏倚。

全部模型以后验采样求解：#r3.sampler.at("chains") 条链、每条 #r3.sampler.at("draws") 次抽样（另有 #r3.sampler.at("tune") 次预热），目标接受率 0.97，随机种子固定。

== 识别性局限（必读） <sec-identifiability>

*三变量的单因子模型是恰好识别（saturated）的*：3 个变量的协方差矩阵有 6 个自由元素（3 个方差 + 3 个协方差），恰好等于 6 个自由参数（3 个载荷 + 3 个独特方差），自由度为零。由此得到两条必须随结论一起陈述的限制：

+ "单因子模型拟合良好"在本设计中*没有证据价值*——它对数据不构成任何约束，不能用来支持"三者同源"这一假设。模型之所以合理，靠的是领域知识（三个序列测的是同一个病灶），而不是统计拟合。
+ 要检验"共因之外是否存在直接通路"，*至少需要第 4 个独立指标*（病理金标准、独立体积测量或另一序列）。模型 C 的 delta 是唯一可用的近似尝试，但它与 L 的载荷互相争夺解释力（见 @sec-model-c），只能作为敏感性分析。

本数据支持"共因结构与数据完全相容"，但*无法排除*额外直接通路的存在。

== 模型 A 参数后验 <sec-model-a>

#figure(
  {
    show table: set text(size: 8pt)
    let rows = csv("data/03_pymc_模型A参数.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [模型 A 参数后验。测量残差为标准差（log 尺度）；带"倍数"的效应量以 1 表示无效应。],
)

#figure(
  image("images/fig12_pymc_forest.png", width: 60%),
  caption: [模型 A 参数后验森林图：点为后验均值、横线为 95%HDI。测量载荷与残差的区间都很窄，而效应量的区间较宽。],
)

关键读数（数值均取自参数表）：

- DWI 载荷 $lambda_D$ = *#pv("lam_d")*[#pl("lam_d"), #pu("lam_d")]：DWI 对真实大小的响应是 SWI 的 #pv("lam_d") 倍，与 1 无实质差异，即在扣除测量噪声后，DWI 与 SWI 是*等比例*的两次测量。
- T2WI 载荷 $lambda_T$ = *#pv("lam_t")*[#pl("lam_t"), #pu("lam_t")]：T2WI 的响应略低于 SWI，符合部分容积效应导致的系统性低估。
- 测量残差（log 尺度）：SWI #pv("sd[0]")、DWI #pv("sd[1]")、T2WI #pv("sd[2]")——T2WI 噪声最大、DWI 噪声最小，与前述灵敏度排序一致。
- 潜变量截距 c = *#pv("c1")*[#pl("c1"), #pu("c1")] 大于 0：真实病灶越大越容易被 T2WI 检出，独立地验证了 MNAR；检出概率在 L = -1 / 0 / +1 处分别为*#pv("p_detect_Lm1")* / *#pv("p_detect_L0")* / *#pv("p_detect_Lp1")*。
- 年龄效应（每增加 10 岁）= *#pv("eff_age_10y")*[#pl("eff_age_10y"), #pu("eff_age_10y")]：年龄每增加 10 岁真实大小的乘性变化，区间覆盖 1。男性效应 = *#pv("eff_male")*[#pl("eff_male"), #pu("eff_male")]，同样覆盖 1——*年龄与性别都无可检出的因果效应*。

#figure(
  image("images/fig10_pymc_latent.png", width: 100%),
  caption: [三个面板分别为 log SWI、log DWI、log T2WI 对潜变量 L 后验均值的散点与拟合线。斜率都在 1 附近，且 DWI 与 SWI 的斜率几乎重合。],
)

== 部位效应 <sec-region>

以额叶为参照，各部位对潜变量 L 的效应：

#figure(
  {
    let rows = csv("data/03_pymc_部位效应.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [模型 A 的部位效应。所有部位的 95%HDI 都覆盖 1，P(倍数大于 1) 都远离 0 或 1。],
)

点估计上颞叶（#(reg.at(1).at("相对参照的倍数")) 倍）、小脑（#(reg.at(4).at("相对参照的倍数")) 倍）看似偏大，但每个亚组只有 5 至 8 例，区间从 0.7 跨越到 3.0；部位效应尺度 τ =#pv("tau_loc") [#pl("tau_loc"), #pu("tau_loc")]的区间也下探到 0，因此*部位对真实大小没有可检出的效应*。

这与探索性分析中"部分容积效应、伪影"的机制假设并不矛盾：部位更可能影响的是*测量误差*而非真实大小，而本设计的样本量不足以分辨两者。

== 直接通路检验（模型 C） <sec-model-c>

在模型 A 之上加入 DWI 到 SWI 的直接项 delta：

$ "log SWI" = nu_1 + L + delta dot "log DWI" + epsilon_1 $

后验结果 delta = *#(r3.model_C_delta.at("mean"))*[95%HDI #(r3.model_C_delta.at("hdi_low")),#(r3.model_C_delta.at("hdi_high"))]，P(|delta| 小于 0.1) = #(r3.model_C_delta.at("p_rope_0.1"))，区间未覆盖 0，看似"存在直接效应"，但同一模型里 DWI 载荷 $lambda_D$ 从模型 A 的#pv("lam_d") [#pl("lam_d"), #pu("lam_d")] 位移到*#(r3.model_C_delta.at("lam_d_in_C"))*（位移 #(r3.model_C_delta.at("lam_d_shift_vs_A"))）：

#figure(
  image("images/fig11_pymc_delta.png", width: 100%),
  caption: [左：delta 的后验分布（紫色阴影为 95%HDI，虚线为 0）；右：模型 A 与模型 C 的 DWI 载荷 $lambda_D$ 后验对比，加入直接项后整体左移。],
)

当同一个 log DWI 既当 L 的指标、又当 log SWI 的解释变量时，参数之间会互相"抢"解释力：delta 的负值正好被 DWI 载荷 $lambda_D$ 的下降所补偿。因此 *delta 不可读作因果效应*，它测量的是"在载荷未被约束变动的情况下，DWI 还能吸收多少协方差"，*结论以模型 A 为准*。

== 收敛诊断与后验预测检验 <sec-diagnostics>

#figure(
  {
    let rows = csv("data/03_pymc_收敛诊断.csv")
    table(
      columns: rows.at(0).len(),
      table.header(..rows.at(0).map(rl).map(strong)),
      ..rows.slice(1).flatten().map(rl),
    )
  },
  caption: [收敛诊断。两个模型都有轻度收敛不足，主因是 DWI 测量残差的标准差。],
)

存在轻度收敛不足：模型 A 的 R-hat 最大#(diag.at(0).at("最大 R-hat"))，发散样本#(diag.at(0).at("发散样本数")) / 10000（约#(int(diag.at(0).at("发散样本数")) / 100)%）。残余的 R-hat 主要来自 DWI 测量残差的标准差（其后验逼近 0 边界形成轻微漏斗），而*关键结论参数*（DWI 载荷、T2WI 载荷、潜变量截距、年龄效应）的 R-hat 均不超过#(pa("lam_d").at("R-hat"))，后验区间在多次运行间稳定。

后验预测检验（log SWI）：

#figure(
  {
    show table: set text(size: 9.8pt)
    table(
      columns: 4,
      align: (auto, center, center, center),
      table.header([*指标*], [*观测值*], [*预测值*], [*判定*]),
      [均值], [#(r3.ppc.at("观测均值"))], [#(r3.ppc.at("预测均值"))], [吻合],
      [标准差], [#(r3.ppc.at("观测SD"))], [#(r3.ppc.at("预测SD"))], [吻合],
      [90% 区间覆盖比例], [—], [#(r3.ppc.at("90%区间覆盖比例"))], [接近名义值 0.90],
    )
  },
  caption: [后验预测检验。模型能复现 log SWI 的一阶与二阶矩，覆盖比例略高于名义值。],
)

由于模型含潜变量，留一法（LOO）模型比较在本设计中不适用，因此以直接通路项 delta 的后验区间与 DWI 载荷的位移作为主要判据。

= 贝叶斯模型对机器学习结论的佐证与补充 <sec-synthesis>

第 @sec-regression 节的回归与去偏估计先给出了若干可检验的经验规律；第 @sec-bayes 节把同一批数据写成显式的数据生成过程，用贝叶斯方法重新估计，下面按两个主题逐条对应。每张表的中列是同一问题在更完整的模型下的复核，右列是机器学习在结构上无法给出、只能由贝叶斯模型补充的部分。

== 序列之间的关系 <sec-relations>

"序列之间到底有没有因果关系"是本次分析的核心。机器学习给出的规律是"高度可预测，但不能读成因果"；贝叶斯模型把直接通路与共同原因两种可能放进同一个生成过程里比较，因此能说明前者为什么不足以支持因果解读。

#figure(
  {
    show table: set text(size: 8.2pt)
    set par(justify: false, leading: 0.6em)
    table(
      columns: (auto, 1fr, 1fr, 1fr),
      align: (auto, left, left, left),
      table.header([*因果问题*], [*机器学习给出的结论*], [*贝叶斯模型的佐证*], [*贝叶斯模型的补充*]),

      [DWI 与 SWI 之间有直接因果通路吗？],
      [弹性 #(r1.naive_beta) #ci(r1.naive_ci)，R² = #(r1.naive_r2)；
        DML 去偏 #(r1.dml.theta)
        #ci((r1.dml.ci95_low, r1.dml.ci95_high))；再加 log T2WI 后区间膨胀 #(r1.ci_width_ratio) 倍（#ci(r1.proxy_ci)），点估计几乎不变——这提示两者的关系来自共同原因],
      [扣除测量噪声后两序列等比例：载荷比 $lambda_D$ = #pv("lam_d")
        [#pl("lam_d"), #pu("lam_d")]，与 1 无实质差异（SWI 锚定为 1），"弹性接近 1"由 L 同时决定两者即可解释，无须直接通路],
      [直接项 delta = #(r3.model_C_delta.at("mean"))，区间不能排除一个小通路；但 DWI 载荷随之位移
        #(r3.model_C_delta.at("lam_d_shift_vs_A"))，说明该位移是参数争夺的产物；贝叶斯模型据此把可识别与不可识别的部分分开陈述，而不再依赖"区间是否包含 0"这一判据],

      [三序列是同源的还是三个独立变量？],
      [VIF 65 至 #(vif.at(0).at("VIF"))；单因子载荷均大于 #(fct.at(0).at("载荷"))，共同方差占比大于 #(fct.at(2).at("共同方差占比(=信度)"))；偏相关仍保留 0.35 至 0.63],
      [测量残差 #pv("sd[0]") / #pv("sd[1]") / #pv("sd[2]") 都很小（log 尺度）；扣除噪声后 DWI 与 SWI 等比例（#pv("lam_d") 对 1），与单因子分析的方向一致],
      [潜变量 L 及其完整后验是贝叶斯模型直接产出、机器学习不具备的量（见 @sec-model-a 节的潜变量后验图）；只有拿到它，才谈得上"真实病灶大小"这一医学构念，以及把三序列读成同一量的三次测量],
    )
  },
  caption: [序列之间关系的逐条对应。机器学习给出相关性证据，贝叶斯模型给出其成因。],
)

由 @sec-relations 可见，机器学习发现的一切（弹性接近 1、加入 T2WI 后区间膨胀、单因子载荷极高）在贝叶斯模型中都得到保留，并被解释为同一潜变量的作用；而"直接通路是否存在"这一机器学习无法回答的问题，贝叶斯模型给出了明确的结构性判断。

== 协变量与缺失机制 <sec-covariates>

第二组的两个问题都属于"数据本身不完整"带来的困难：协变量的微弱效应容易被样本量掩盖，而 T2WI 的缺失本身携带信息，这两点恰恰是贝叶斯模型能补足机器学习的地方。

#figure(
  {
    show table: set text(size: 8.2pt)
    set par(justify: false, leading: 0.6em)
    table(
      columns: (auto, 1fr, 1fr, 1fr),
      align: (auto, left, left, left),
      table.header([*因果问题*], [*机器学习给出的结论*], [*贝叶斯模型的佐证*], [*贝叶斯模型的补充*]),

      [年龄、性别、部位影响病灶大小吗？],
      [系数接近 0（年龄 z 分 #(r1.adj_coefs.at("age_z"))、性别 #(r1.adj_coefs.at("sex"))、幕上 #(r1.adj_coefs.at("supra"))）；置换重要性接近 0
        （最大 #(perm.at(0).at("重要性均值"))）],
      [年龄效应（每 +10 岁）= #pv("eff_age_10y")
        [#pl("eff_age_10y"), #pu("eff_age_10y")]；男性效应 = #pv("eff_male")
        [#pl("eff_male"), #pu("eff_male")]；五个非参照部位的倍数 95%HDI 全部覆盖 1],
      [把"无信号"表述为效应量的区间，而不只是显著性判定；并把机器学习未单列的部位效应逐一给出区间（各亚组 5 至 8 例，故区间较宽），这正是"未检出效应"与
        "效应确实很小"两种表述的分界],

      [T2WI 缺失是随机还是与大小相关？],
      [未检出组尺寸显著更小（未检出的逻辑回归 CV AUC = #(r1.mnar_auc)）；
        T2 未检出组的 DWI / SWI 中位数 3.55 / 3.80，对检出组 7.70 / 7.80],
      [潜变量截距 c = #pv("c1") [#pl("c1"), #pu("c1")] 大于 0；检出概率随 L 从 #pv("p_detect_Lm1") 升到 #pv("p_detect_Lp1")，即缺失概率随真实病灶增大而单调上升],
      [机器学习只能把缺失*检出来*，无法纳入估计；贝叶斯模型把它写成选择方程并入似然，缺失机制因此从"必须回避的偏倚来源"变成"模型的一个成分"——这也是本报告中
        T2WI 方程可以只用检出子集拟合而不引入偏倚的原因],
    )
  },
  caption: [协变量与缺失机制的逐条对应。右列两项是机器学习结构上无法给出的信息。],
)

因此两者的关系不是"两套方法互相争辩"，而是同一批数据上的分工与接续：回归与去偏估计负责*可预测性与经去偏的关联强度*，贝叶斯潜变量模型负责*结构*。前者能给出
"用 DWI 预测 SWI 可以做到 R² = #(cvp.at(0).at("CV R2 均值"))"，后者才把这句话解释成"这个数字来自共同原因，而不是 DWI 决定 SWI"，并补上测量误差、潜变量后验与缺失机制三件前者拿不出的东西。

需要如实说明一点：两个模型共用同一批数据、假设部分重叠，因此上面两表的"佐证"是
*一致性*而非独立复现。它排除了"换一种估计方式结论就翻转"这一可能，但不等价于外部验证——外部验证需要新的样本。

= 结论与局限 <sec-conclusion-limits>

== 结论 <sec-findings>

+ *三个序列测的是同一件事，而不是三个彼此独立的指标。* T2WI、DWI、SWI 上的最大径，本质上是同一个"真实病灶大小 L"量了三遍，每一遍都多带一点测量误差。四条证据指向同一个方向：三者两两相关高达 0.986 至 0.995；把它们一起放进一个回归方程，信息冗余到分不清各自的贡献（VIF 都在 65 以上，log DWI 达 #(vif.at(0).at("VIF"))，而通常希望低于 5）；因子分析里公共成分占绝对主导，各序列的载荷都在 0.99 以上、自己独有的成分不到 2%；贝叶斯模型扣掉噪声之后，剩下的测量误差也只有 #pv("sd[1]") 至 #pv("sd[2]")（对数尺度），而且 DWI 与 SWI 对真实大小的响应几乎没有差别。
+ *"DWI 能预测 SWI"不等于"DWI 导致 SWI"。* 两者几乎一对一地同步变化（弹性约 0.98），但这更像是同一个病灶大小在同时决定这两个读数——两个数字一起变大变小，背后往往是同一个原因在推动，而不是其中一个带出了另一个。数据真正支持的因果关系只有两条：真实病灶大小决定三个序列上读到什么数；真实病灶大小决定 T2WI 能不能被检出。
+ *年龄、性别、病灶部位都没有影响真实病灶大小的证据。* 机器学习与贝叶斯模型在多种设定下算出的效应量都贴近"没有作用"，区间也都把"没有作用"包含在内。
+ *T2WI 的缺失不是随机的，不能当普通的缺失值补掉。* 病灶越小越容易漏检：本样本中，检出概率随真实病灶由小到大而从 #pv("p_detect_Lm1") 升到 #pv("p_detect_Lp1")。"缺失"和"病灶小"绑在一起，这层关系必须写进模型本身（作为一条独立的"能否检出"方程），否则偏倚会跟着进入结果。
+ *同一位患者的多个病灶之间没有额外的关联。* 同一位患者不同病灶的相似程度可以忽略（ICC(1) 为 #(iccs.at(0).at("ICC(1)")) 与 #(iccs.at(1).at("ICC(1)"))），设计效应 #(iccs.at(0).at("设计效应")) 也接近 1；按病灶分析还是按患者分析，结论一致，不必再套一层患者层面的模型。
+ *仍然无法排除"DWI 在共同原因之外还有一条直接通路"。* 这是数据本身能回答的范围所限，不是方法没做到，详见下面"局限"第一条。

== 局限 <sec-limits>

- *模型能回答的问题有上限。* 三个变量共用一个因子的模型没有多余的自由度，所以"拟合得好"不能拿来证明"三者同源"——同源这个判断来自医学常识（三个序列量的是同一个病灶），而不是来自统计。要把"共同原因"和"额外的直接通路"分开，至少还需要第四个独立指标（病理金标准、独立体积测量或另一条序列）。
- *样本量偏小。* #r1.n_lesion 个病灶 / #r1.n_patient 位患者，按部位分组后每组只有 5 至 8 例，所以各种效应量的区间都很宽。"没有检出效应"不等于"确实没有效应"，中等强度的真实效应也可能被漏掉。
- *回顾性观察数据。* 病灶存在了多久、有没有出过血、遗传背景等都没有记录，这些看不见的因素无法排除。
- *抽样尚未完全收敛。* 最大 R-hat 为 #(diag.at(0).at("最大 R-hat"))（通常希望低于 1.01），约 #(int(diag.at(0).at("发散样本数")) / 100)% 的抽样需要丢弃，主要来自 DWI 的测量误差贴着参数边界。结论所依赖的关键参数不受影响，但很小的效应量不宜过度解读。
- *分不清"真的更大"还是"测得更不准"。* 部位也可能主要影响测量误差而不是真实大小，本设计无法把这两种情况分开。
- *数据本身有一处缺陷。* @sec-coefficient 节末已经说明：响应变量被一并放进了自变量矩阵，因此共线性表与正则化系数表都不能再当作预测能力的证据。
