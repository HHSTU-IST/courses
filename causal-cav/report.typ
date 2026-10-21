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

// 结果长表（sklearn 分析产出的全部标量）
#let r1 = res("data/02_sklearn_results.csv")

// 正文里会引用的那几张表的取值源（每个都是一行一条记录）
#let vif = dicts("data/02_VIF.csv")
#let cvp = dicts("data/02_CV性能.csv")
#let fct = dicts("data/02_单因子模型.csv")
#let iccs = dicts("data/02_聚类结构ICC.csv")
#let perm = dicts("data/02_置换重要性.csv")

// 区间文本，如 [0.9487, 1.0246]。参数有两种来源：结果长表里成对的
// 「<键>.下 / <键>.上」（读回来是字典），或正文里显式写出的两个标量（数组）。
#let ci(v) = {
  let pair = if type(v) == dictionary { (v.at("下"), v.at("上")) } else { (v.at(0), v.at(1)) }
  "[" + str(pair.at(0)) + ", " + str(pair.at(1)) + "]"
}

// =========================================================================== //
// 封面区
// =========================================================================== //
#align(center)[
  #v(0.4cm)
  #text(size: 17pt, weight: "bold", font: ("Noto Sans SC",), fill: rgb("#1f4e79"))[
    DWI / SWI 在颅内海绵状血管瘤诊断中的因果关系分析 \
  ]
  #v(0.15cm)
  #text(size: 11pt, fill: luma(80))[结果汇总报告：回归与双重机器学习去偏估计]
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
      [*方法*], [回归与双重机器学习去偏估计（相关、共线性、偏相关骨架、单因子与置换重要性）],
      [*核心结论*],
      [T2WI、DWI、SWI 三个序列测的是同一个"真实病灶大小"的三次带噪测量；DWI 对 SWI 的弹性接近 1，控制协变量与双重机器学习去偏后均不下降，指向共同原因],
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
- *SWI*：对含铁血黄素与钙化最敏感，检出率最高（无缺失），通常测得范围最大。

== 预处理决策 <sec-preprocessing>

- 患者标识：按病例序号归组，得到 #r1.n_patient 位患者 / #r1.n_lesion 个病灶。
- T2WI、DWI 中未检出的记录记为缺失值，语义是"该序列未检出该病灶"。
- 部位缺失 1 例（患者 18 的第 2 个病灶）用同患者其它病灶的部位补齐；其余不做插补。
- 三个尺寸变量取对数（log T2WI、log DWI、log SWI），系数解释为弹性。
- 性别编码 男 1 / 女 0；派生出幕上（1）与左右侧（左 1 / 右 0 / 中线 -1）。
- *不做单值插补*：T2WI 缺失与病灶大小强相关（下一节验证为 MNAR），插补会引入偏倚；因此保留缺失标记，并在解读结果时始终考虑这一机制。

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
    *结论：T2WI 缺失属于 MNAR（非随机缺失）。* 缺失概率依赖潜变量"真实病灶大小"本身，因此单值插补、或用完整病例直接代表全体都会引入偏倚；本报告因此保留缺失标记、不做插补，并把这一点作为解读全部结果时的前提。
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

三者的共同方差占比都超过 98%，也就是说它们在测量同一个东西。但必须立刻补充一条限定：*这一单因子解在本设计中是恰好识别的，因而"拟合良好"不构成证据*。

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

= 结论与局限 <sec-conclusion-limits>

== 结论 <sec-findings>

T2WI、DWI、SWI 上的最大径是同一个真实病灶大小 L 量出来的三个读数，每一层测量都自带一点误差。三者两两相关落在 0.986 至 0.995 之间；把三个变量一起放进回归方程，各自的贡献就分不开了，VIF 全部超过 65（log DWI 达 #(vif.at(0).at("VIF"))，通常希望低于 5）。换成因子分析看同一组径线，结果还是一样：各序列在公因子上的载荷都在 0.99 以上，留给自己独有的成分不到 2%。

弹性约 0.98 只说明两个读数同步变化，病灶大小同时推动 DWI 与 SWI 就能解释这一点。能站得住的因果关系是真实病灶大小决定三个序列读到什么数值，也决定 T2WI 能不能检出。年龄、性别、部位在各种设定下算出的效应量都贴近无效应的位置，区间也覆盖该位置，因此没有证据表明它们影响真实病灶大小。数据同样无力排除 DWI 在共同原因之外还有一条小的直接通路，这条限制来自设计本身，见下一节第一条。

同一位患者多个病灶之间的相关可以忽略（ICC(1) 为 #(iccs.at(0).at("ICC(1)")) 与 #(iccs.at(1).at("ICC(1)"))，设计效应 #(iccs.at(0).at("设计效应")) 也接近 1），患者级自助区间 #ci(r1.naive_ci_cluster) 与病灶级 #ci(r1.naive_ci) 几乎重合，所以不必再套一层患者层面的模型。

T2WI 的缺失与病灶大小绑定：未检出组的 DWI / SWI 中位数只有 3.55 / 3.80 mm，检出组为 7.70 / 7.80 mm，用 log DWI 与 log SWI 预测是否未检出的五折交叉验证 AUC 达 #(r1.mnar_auc)。这类缺失既不适合单值插补，也不能默认完整病例代表全体，否则偏倚会跟着进入结果。

== 局限 <sec-limits>

三个变量共用一个因子时自由度为零，拟合得好并不能证明三者同源；这个判断来自医学常识（三个序列量的是同一个病灶），统计本身给不出。要把共同原因与额外的直接通路区分开，至少还需要第四个独立指标，例如病理金标准、独立的体积测量或另一条序列。

样本量限制了能支持的结论：#r1.n_lesion 个病灶来自 #r1.n_patient 位患者，按部位分组后每组只有 5 至 8 例，效应量的区间普遍很宽，未检出效应与效应确实很小难以分辨。这是回顾性观察数据，病灶存在了多久、有没有出过血、遗传背景都没有记录，未观测因素的影响无从排除。部位上另有一处模糊，它可能主要影响测量误差而不是真实大小，当前设计分不开这两种情形。

数据本身还有一处缺陷：@sec-coefficient 节末已经说明，响应变量被一并放进了自变量矩阵，因此共线性表与正则化系数表都不能当作预测能力的证据。
