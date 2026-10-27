# Markdown 教程 2

## 链接

### 超链接

```markdown
[百度](http://baidu.com)
```

[百度](http://baidu.com)

### 图片

```markdown
![图片 alt](图片地址)
```

这里图片 `alt` 就是显示在图片下面的文字，相当于对图片内容的解释

![知乎](https://pic2.zhimg.com/80/v2-48bbd284deacef0b5896427e660b2a51_1440w.png)

### 文件内跳转

```markdown
[跳转到通用格式](#高亮)
```

[跳转到通用格式](#高亮)

### 文件间跳转

```markdown
[[文件名#标题]]
```

Markdown 代码、公式语法请参考 [[md-01-base#代码]]。

### 目录

- [链接](#链接)
  - [超链接](#超链接)
  - [图片](#图片)
  - [文件内跳转](#文件内跳转)
  - [文件间跳转](#文件间跳转)
  - [目录](#目录)
- [扩展语法](#扩展语法)
  - [脚注](#脚注)
  - [表情](#表情)
- [HTML](#html)
  - [下划线](#下划线)
  - [高亮](#高亮)
  - [字体颜色和字号](#字体颜色和字号)
  - [内容居中](#内容居中)
  - [表格跨行](#表格跨行)
  - [表格跨列](#表格跨列)
- [CSS](#css)
  - [引入](#引入)
  - [自定义高亮](#自定义高亮)
  - [自定义列表](#自定义列表)
  - [自定义表格](#自定义表格)
  - [自定义标注](#自定义标注)
  - [流式分栏](#流式分栏)
  - [预设分栏](#预设分栏)

## 扩展语法

### 脚注

```markdown
文本[^标记序号]...。

[^标记序号]: ...
```

2004 年，Wolfram 的研究助理 Matthew Cook 证明了初等 CA 中的规则 110 是通用的 [^1]，即，任何计算机可完成的任何计算都可由该 CA 完成。

[^1]: Cook, M. "Universality in Elementary Cellular Automata." Complex Systems 15, 1-40, 2004.

### 表情

🐱 🚲 🍦 🏃 🎿

## HTML

<link rel="stylesheet" type="text/css" href="md.css">

### 下划线

```markdown
<u>下划线</u>
```

<u>下划线</u>

### 高亮

```markdown
<mark>高亮</mark>
```

<mark>高亮</mark>

### 字体颜色和字号

```markdown
<font color="red" size="5">红色字体</font>
```

<font color="red" size="5">红色字体</font>

### 内容居中

```html
<center>
内容
</center>
```

<center>

| 标签/属性 |       功能/作用        |
| :-------: | :--------------------: |
| `<table>` |      定义表格容器      |
|  `<tr>`   |       定义表格行       |
|  `<th>`   |     定义表头单元格     |
|  `<td>`   |     定义数据单元格     |
| `colspan` | 跨列合并单元格（属性） |
| `rowspan` | 跨行合并单元格（属性） |
| `border`  |    边框样式（属性）    |

</center>

### 表格跨行

```html
<table border="1">
  <tr>
    <th rowspan="2">索引</th>
    <td>内容 A</td>
  </tr>
  <tr>
    <td>内容 B</td>
  </tr>
</table>
```

<table border="1">
  <tr>
    <th rowspan="2">索引</th>
    <td>内容 A</td>
  </tr>
  <tr>
    <td>内容 B</td>
  </tr>
</table>

### 表格跨列

Markdown 原生不支持对齐控制，可通过 `<th style="text-align: ...">` 实现。

```html
<table border="2">
  <tr>
  <th colspan="2" style="text-align: center;">表头</th>
  </tr>
  <tr>
    <td>单元格 1</td>
    <td>单元格 2</td>
  </tr>
</table>
```

<table border="2">
  <tr>
  <th colspan="2" style="text-align: center;">表头</th>
  </tr>
  <tr>
    <td>单元格 1</td>
    <td>单元格 2</td>
  </tr>
</table>

## CSS

### 引入

CSS 是在 HTML 4 开始使用的，是为了更好的渲染 HTML 元素而引入的。CSS 可以通过以下方式添加到 HTML 中：

- 内联样式：在 HTML 元素中使用`"style"` 属性
- 内部样式表：在 HTML 文档头部`<head>`区域使用`<style>` 元素来包含 CSS
- 外部引用：使用外部 CSS 文件

```html
<link rel="stylesheet" type="text/css" href="style.css">
```

<link rel="stylesheet" type="text/css" href="styles/md.css">

### 自定义高亮

```css
mark {
    background-color: #f8efbfca;
    color: #8b0644ff;
}
```

Markdown 支持直接嵌入 <mark>HTML</mark> 代码，可以实现更复杂的样式。

### 自定义列表

```css
ol {
    list-style-type: trad-chinese-informal;
}

ol ol {
    list-style-type: lower-latin;
}
```

1. 中文计数
   1. 二级有序列表
2. 继续计数

### 自定义表格

- `table`
  - `width`: px | percentage
- `th`, `td`
  - `border`
  - `padding`: px
  - `text-align`: left | right | center

```css
table {
    width: 100%;
}

th,
td {
    border: 1px solid #ddd;
    padding: 12px;
    text-align: center;
}

tr:nth-child(even) {
    background-color: #f2f2f2;
}
```

### 自定义标注

```css
.quote {
    background-color: #eff9f9ff;
    padding: 15px;
    border-left: 4px solid #b2b7d9ff;
    margin-left: 15px;
    margin-right: 15px
}
```

<div class="quote">
  块级代码需要写在<code>div</code>标签内。
</div>

```html
<div class="quote">
  内容
</div>
```

### 流式分栏

```css
.text-columns {
    columns: 2;
    column-gap: 30px;
    height: 160px;
    column-rule: 1px dashed #ccc;
    padding: 10px;
}
```

```html
<div class="text-columns">
内容
</div>
```

<div class="text-columns">
这是一段长文本，会自动分配到两栏中。当内容超过一栏高度时，剩余部分会自动流入第二栏。

支持 Markdown 语法，比如 **加粗**、*斜体* 或列表：

- 列表项 1
- 列表项 2

这种布局适合纯文本为主的内容，自动平衡各栏长度，无需手动拆分内容。

</div>

### 预设分栏

```css
.two-columns {
    display: flex;
    gap: 10px;
    width: 100%;
    height: 100px;
}

.column {
    flex: 1;
}
```

```html
<div class="two-columns">
  <div class="column">
    左栏内容
  </div>
  <div class="column">
    右栏内容
  </div>
</div>
```

<div class="two-columns">
  <div class="column">
   这是一段长文本。预设分栏不同于流式分栏。
  </div>
  <div class="column">
    不支持支持 Markdown 语法，比如 **加粗**、*斜体* 或列表。
  </div>
</div>
