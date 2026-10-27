# Markdown 基础

## 环境配置

1. 打开 PowerShell，输入 `winget install vscode`
2. 在 VSCode 中找到侧边栏的扩展商店（图标为四个矩形）
3. 搜索并安装扩展
4. 点击打开文件夹，新建文件夹，并选择（此时 VSCode 会重启）
5. 找到文件夹，新建 .md 文件（图标右下角有 + 号）

## 语法扩展

VSCode 默认是支持 Markdown 的，但还是有必要安装下面的扩展提高写作效率。

- Markdown All In One
- rumdl

### Markdown All in One

如名称所述，这是个大一统型的扩展，集成了撰写 Markdown 时所需要的大部分功能，是 Markdown 类插件中下载榜榜首。可认为是 VSCode 中的 Markdown 必备扩展。其功能涵盖：

- 快捷命令及代码片
- 自动生成标题编号
- 自动生成并更新目录
- LaTeX 数学公式支持

![Markdown All in One](https://pic2.zhimg.com/80/v2-48bbd284deacef0b5896427e660b2a51_1440w.png)

加入配置（打开settings.json）

```json
{
    "[markdown]": {
    "editor.defaultFormatter": "yzhang.markdown-all-in-one",
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit"
    },
    "editor.quickSuggestions": {
      "other": "on",
      "comments": "off",
      "strings": "off"
    }
  },
  "markdown.extension.toc.levels": "2..4",
}
```

### rumdl

rumdl 是个功能强大的 Markdown 语法检查器（linter）和格式化器（formatter），可以帮助你书写出规范的文档，同时避免书写错误导致文档无法渲染。个人观点，认为这个也是必装扩展。

```json
{
  "rumdl.rules.disable": [
    "MD013",
    "MD025",
    "MD029",
    "MD033"
  ],
}
```

## 作业要求

使用 Markdown 实现本文档内分割线以下部分包含的各种样式

- 标题和字体
  - [ ] 标题层级正确（10 分）
  - [ ] 加粗（5 分）
  - [ ] 斜体（对人名均采用斜体，5 分）
  - [ ] 删除线（5 分）
- 列表
  - [ ] 有序列表（5 分）
  - [ ] 无序列表（5 分）
  - [ ] 嵌套列表（5 分）
- 块
  - [ ] 行内代码（5 分）
  - [ ] 块级代码（10 分）
  - [ ] 引用（5 分）
  - [ ] 标注（5 分）
- 表格和公式
  - [ ] 表格（10 分）
  - [ ] 表格对齐（5 分）
  - [ ] 行内公式（5 分）
  - [ ] 块级公式
    - [ ] 极限和积分（5 分）
    - [ ] 方程组（5 分）
    - [ ] 矩阵（5 分）

作业以 .md 文件提交，文件命名模式为：`01-学号-姓名.md`。

---

## Markdown（二级标题）

Markdown 是一种轻量级的**标记语言**（已加粗），由 *John Gruber*（1973～）与 *Aaron Swartz*（1986～2013）于 2004 年创造，被网站用于编写说明文件（README）、技术文档或在论坛上发布信息。由于其语法简单，易于读写，且编写出的作品简洁美观，目前也被越来越多的人群用于日常写作、发布电子书甚至书写电子邮件。

自从有了 Markdown，我们便不必总是使用 ~~Word~~ 了。

### Markdown 的优势（三级标题）

简单说，Markdown 有如下优势：

1. 语法简单，易于学习
2. 简洁美观，可读性好
3. 兼容 HTML/CSS，可添加丰富的样式
4. 易于部署

### 通用格式（三级标题）

通用格式包括

- 文本
  - 标题
  - 字体
- 代码
- 公式

### 代码（三级标题）

如下是 Python 中 `f-string`（此为行内代码格式，非高亮格式）语法的一个例子。

```python
price = 59
txt = f"The price is {price} dollars"
print(txt)
```

## 微积分与线性代数入门（二级标题）

> 数学的本质在于其自由。—— 格奥尔格·康托尔

本教程将通过 Markdown 格式，结合具体数学知识，演示引用、表格、[LaTeX 公式](https://www.cnblogs.com/nowgood/p/Latexstart.html)等样式的使用，帮助你同时掌握数学基础与排版技巧。

> [!NOTE] LaTeX 公式
> 目前 Markdown 也已经支持 LaTeX 语法的公式。在 LaTeX 数学模式中，公式有两种形式——行内公式和行间公式。前者公式嵌入在行内，适用于简单短小的公式；后者居中独占一行，适用于比较长或重要的公式。

| 说明  | 语法  |  示例   |
| :---: | :---: | :-----: |
| 上标  |  a^b  | $a^{b}$ |
| 下标  |  a_b  | $a_{b}$ |

### 极限（三级标题）

极限是微积分的基础，用于描述“变量无限趋近于某值时函数的趋势”。例如：

重要极限

$$
\lim_{x → \infty}\left(1 + \frac{1}{x}\right)^x = e
$$

其中，$e$是自然常数，约等于$2.71828$，是指数函数$e^x$的底数。

### 积分（三级标题）

定积分可计算“区间上的总量”，如：

$$
\int_{0}^{2} (x^2 - 2x + 2) dx = \frac{8}{3}
$$

### 方程组（三级标题）

狄利克雷函数是一个定义在实数集上的特殊函数，数学家狄利克雷以其名字命名。它的值在有理数处为$1$，在无理数处为$0$。该函数是典型的“病态函数”，在任意点处都不连续、不存在极限，且黎曼不可积但勒贝格可积。

$$
\begin{cases}
1 & x \text{为有理数} \\
0 & x \text{为无理数}
\end{cases}
$$

### 矩阵（三级标题）

范德蒙矩阵是法国数学家范德蒙（Alexandre-Théophile Vandermonde，1735～1796）提出的一种各列为几何级数的矩阵。其形式为：每一行对应于一个点在不同幂次下的值，即第$i$行、第$j$列的元素可表示为$\alpha_i^{(j-1)}$，其中，$\alpha_1, \alpha_2,..., \alpha_n$两两互异。该矩阵在数学和计算科学中有着广泛的应用。

$$
V=
\begin{pmatrix}
1 & \alpha_1 & \alpha_1^2 & … & \alpha_1^{n-1} \\
1 & \alpha_2 & \alpha_2^2 & … & \alpha_2^{n-1} \\
\vdots & \vdots & \vdots & \ddots & \vdots \\
1 & \alpha_m & \alpha_m^2 & … & \alpha_m^{n-1}
\end{pmatrix}
$$
