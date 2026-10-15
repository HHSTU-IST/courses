# Markdown 教程 1

## 基础格式

### 标题

### 字体

```markdown
**这是加粗的文字**

*这是倾斜的文字*

***这是斜体加粗的文字***

~~这是加删除线的文字~~。
```

**这是加粗的文字**

*这是倾斜的文字*

***这是斜体加粗的文字***

~~这是加删除线的文字~~。

### 分割线

```markdown
---
```

---

## 列表

### 无序列表

- 无序列表

### 有序列表

```markdown
1. 列表内容
2. 列表内容
3. 列表内容
```

1. 列表内容
2. 列表内容
3. 列表内容

### 列表嵌套

上一级和下一级之间敲**3 个空格**即可

```markdown
- 一级无序列表内容
  - 二级无序列表内容
  - 三级无序列表内容
    - 四级无序列表内容
```

- 一级无序列表内容
  - 二级无序列表内容
  - 三级无序列表内容
    - 四级无序列表内容

### 复选框（扩展语法）

```markdown
- [ ] 未完成
- [x] 已完成
```

- [ ] 未完成
- [x] 已完成

## 代码

### 行内代码

```markdown
这是`行内代码`。
```

这是`行内代码`。

### 块级代码

```python
import functools


@functools.lru_cache
def fibonacci(n):
    return n if n < 2 else fibonacci(n - 2) + fibonacci(n - 1)


if __name__ == "__main__":
    print(fibonacci(4))
```

## 块级格式

### 引用

- 在引用的文字前加>即可
- 引用也可嵌套，如 `>>`，`>>>`

```markdown
> 这是引用的内容
>> 这是嵌套引用内容
```

> 这是引用的内容
>> 这是嵌套引用内容

### 标注

> [!note] 标注
>
> Callout 又称 标注，是 Obsidian 率先引入的块状引用语法。VSCode 随后部分支持，后者支持的标签有：
>
> - note
> - warning
> - tip
> - caution
> - important

## 表格

| 名字   |    姓氏 |           电子邮件           |
| :----- | ------: | :--------------------------: |
| John   |     Doe |    <john.doe@example.com>    |
| Muffin | Poppies | <muffin.poppies@example.com> |
| Jane   |     Doe |    <jane.doe@example.com>    |

- 第二行分割表头和内容
- 文字默认居左
- `:-:`：表示文字居中
- `:--`：表示文字居左
- `--:`：表示文字居右

## 公式

### 基础语法

|  说明  | 语法                      | 示例                            |
| :----: | ------------------------- | ------------------------------- |
|  上标  | `a^b`                     | $a^{b}$                         |
|  下标  | `a_b`                     | $a_{b}$                         |
|  乘号  | `\times`, `\cdot`, `\ast` | $\times$, $\cdot$, $\ast$       |
| 约等于 | `\approx`                 | $\approx$                       |
|  极限  | `\lim_{n\to\infty}{数列}` | $\lim_{n\to\infty}{a_{n}}$      |
|  求和  | `\sum_{起始}^{结束} 算式` | $\sum_{i=1}^{n}X_n$             |
|  积分  | `\int_{下界}^{上界} 算式` | $\int_{a}^{b}f\left(x\right)dx$ |

### 行内公式

```markdown
这是行内公式 $\Gamma(n) = (n-1)! \quad \forall n \in \mathbb{N}$。
```

这是行内公式 $\Gamma(n) = (n-1)! \quad \forall n \in \mathbb{N}$。

### 块级公式

- 极限

```latex
$$
\lim_{n\to -\infty}\frac{1}{n}
$$
```

$$
\lim_{n\to -\infty}\frac{1}{n}
$$

- 积分

```latex
$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$
```

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

- 方程组

```latex
$$
\begin{cases}
x + 2y = 1 \\
3x - y = 0
\end{cases}
$$
```

$$
\begin{cases}
x + 2y = 1 \\
3x - y = 0
\end{cases}
$$

- 矩阵

```latex
$$
A =
\begin{bmatrix}
a_{11} & a_{12} & a_{13} \\
a_{21} & a_{22} & a_{23} \\
a_{31} & a_{32} & a_{33}
\end{bmatrix}
$$
```

$$
A =
\begin{bmatrix}
a_{11} & a_{12} & a_{13} \\
a_{21} & a_{22} & a_{23} \\
a_{31} & a_{32} & a_{33}
\end{bmatrix}
$$
