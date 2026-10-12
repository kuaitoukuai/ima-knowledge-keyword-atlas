# Excel 呈现要点与踩坑

## 六视图布局（`06_build_workbook.py` 已实现）

| 视图 | 结构 | 用途 | 打印 |
|---|---|---|---|
| ① 总览矩阵 | 维度 × 关键词 网格，带 `D01-01` 编号 | 一页纸目录 | A4 横向 fitToPage 1×1 |
| ①B 总览(含子关键词) | 同网格，每格父关键词下展开子关键词（富文本） | 一屏纵览全貌 | A4 横向 fitToWidth=1 / fitToHeight=0，纵向续页 |
| ② 关键词展开 | 1 父关键词 = 1 行，子关键词格内换行 | 逐条通读 | — |
| ③ 子关键词明细 | 1 子关键词 = 1 行，含说明、来源、日期，带筛选 | 检索/当字典 | A4 横向，纵向续页 |
| ④ 文档溯源索引 | **全部**源文档逐篇列出，标注被引用与否 | 反向倒查出处 | A4 横向，纵向续页 |
| ⑤ 维度统计 | 各维度规模 + 柱状图 | 看结构分布 | — |

## 关键技巧

### 同一格内「父关键词加粗 + 子关键词换行」用富文本

openpyxl ≥3.1 支持单元格富文本：

```python
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont

rt = CellRichText()
rt.append(TextBlock(InlineFont(rFont="微软雅黑", sz=9, b=True), parent))
for i, kw in enumerate(sub_kws):
    rt.append(TextBlock(InlineFont(rFont="微软雅黑", sz=8), f"\n{i+1}. {kw}"))
cell.value = rt
```

- 读回来校验时要加 `rich_text=True`，否则得到的是拼接后的普通字符串：
  `openpyxl.load_workbook(f, rich_text=True)`，然后检查每段 `block.font.b`。
- 一定要留 try/except 降级：拿不到富文本 API 时写成普通字符串，别让整表失败。

### 行高要自己算

openpyxl 不会自动适配换行文本的行高。按显示宽度估算折行数：

```python
def est_lines(text, units_per_line):
    n = 0
    for line in text.split("\n"):
        # 中日韩字符按 2 个单位宽、ASCII 按 1 个
        u = sum(2 if ord(ch) > 0x2E80 else 1 for ch in line)
        n += max(1, -(-u // units_per_line))
    return n

ws.row_dimensions[r].height = est_lines(text, col_width - 1) * 11.6 + 6
```

### 一页纸放不下就别硬压

把上百个子关键词塞进 10×10 网格，实测 A4 横向要 **约 2.6 页**。
强行 `fitToHeight=1` 会把字号压到 5pt 左右（不可读）。
**正确做法**：`fitToWidth=1` + `fitToHeight=0` 让它纵向续页，并把页数如实告诉用户。

### 打印设置三件套

```python
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.page import PageMargins

ws.print_area = "A1:K14"
ws.page_setup.orientation = "landscape"
ws.page_setup.paperSize = ws.PAPERSIZE_A4
ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 0          # 0 = 不限高，纵向续页
ws.page_margins = PageMargins(0.28, 0.28, 0.3, 0.3, 0.15, 0.15)
ws.print_options.horizontalCentered = True
ws.print_title_rows = "1:3"            # 每页重复表头
ws.freeze_panes = "B4"                 # 冻结首列 + 表头
```

## 踩坑清单

### 1. 不要用公式 —— 预览环境不会重算

openpyxl 写进去的公式只是字符串、没有缓存值。`pandas`、`data_only=True`、以及多数在线预览器
（含微信/邮件附件预览）读到的都是 **空白**。本机若没有 LibreOffice、也没装 `formulas` 包，就无法补缓存值。

**对策**：这类「静态速览表」直接在 Python 里算好结果写进去，别写公式。
如果确实需要公式联动，先确认环境能重算（`recalc.py` 返回 `status=success`），否则不要交付。

### 2. 目标文件被占用会 `PermissionError`

```
PermissionError: [Errno 13] Permission denied: '...xlsx'
```

用户在预览器/Excel 里打开着这个文件时就写不进去，删掉 `~$xxx.xlsx` 锁文件也**无效**（锁属主是外部进程）。

**对策**：脚本里 try/except，失败就另存为 `<name>_v2.xlsx`，并明确告诉用户。
交付前也可以先用 `open(path, 'r+b')` 试一下可写性。

### 3. 中文列宽与「一页装下」的换算

Excel 列宽单位 ≈ 1 个默认字体字符宽：`像素 ≈ 宽 × 7 + 5`，A4 横向可打印宽约 11.19 英寸 ≈ 1075 px。
所以 `10 列 × 宽 14 + 标签列 16` ≈ 1147 px → 需要缩到 **约 94%** 才够一页。据此估算缩放，别凭感觉调。

### 4. 筛选 + 冻结要在正确的行

有标题行时表头不在第 1 行：`freeze_panes` 要设在表头**下一行**（如 `"A3"`），
`auto_filter.ref` 从表头行开始（如 `A2:H581`）。

### 5. 配色

默认商务蓝：表头 `#4472C4` + 白字；维度标签列 `#D9E2F3`；隔行浅底 `#F5F8FD`；
边框 `#9DB2D4`。同一表最多「主色 + 浅底 + 警示色」三种，别继续加。
打印场景靠 **边框 + 加粗** 建立层级，颜色只作辅助（黑白打印也要能看）。
