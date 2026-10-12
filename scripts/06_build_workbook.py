#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06_build_workbook.py —— 把关键词体系渲染成多视图 Excel（一次生成 6 个视图）

视图：
  ①  总览矩阵            维度 × 关键词 网格（一页纸可打印目录，带 D01-01 编号）
  ①B 总览(含子关键词)     同网格，但每格在父关键词下直接列出子关键词（富文本，父词加粗）
  ②  关键词展开           每个父关键词一行，子关键词格内换行 + 主要来源文档
  ③  子关键词明细         每条子关键词一行，可筛选，含说明、来源 md、日期
  ④  文档溯源索引         md 目录下**全部**文档逐篇列出，标注被引用与否、支撑了哪些编号
  ⑤  维度统计             各维度规模 + 柱状图

用法：
  python3 06_build_workbook.py --merged <merged.json> --md <md目录> --out <xlsx> \
      [--title "..."] [--subtitle "..."]
"""
import argparse, json, os, re, sys

try:
    import openpyxl
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl>=3.1.0"])
    import openpyxl

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties
from openpyxl.worksheet.page import PageMargins
from openpyxl.chart import BarChart, Reference

ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5", "latin-1")


def xl(h):
    v = h.removeprefix("#").upper()
    if len(v) != 6:
        raise ValueError(h)
    return "FF" + v


C = dict(title_bg=xl("#2F5597"), head_bg=xl("#4472C4"), dim_bg=xl("#D9E2F3"),
         band=xl("#F5F8FD"), white=xl("#FFFFFF"), border=xl("#9DB2D4"),
         text=xl("#1A1A1A"), sub=xl("#5A5A5A"), grey=xl("#9A9A9A"))
thin = Side(style="thin", color=C["border"])
B_ALL = Border(left=thin, right=thin, top=thin, bottom=thin)
F_TITLE = Font(name="微软雅黑", size=13, bold=True, color=C["white"])
F_SUB = Font(name="微软雅黑", size=8.5, color=C["sub"])
F_HEAD = Font(name="微软雅黑", size=9, bold=True, color=C["white"])
F_DIM = Font(name="微软雅黑", size=9, bold=True, color=C["text"])
F_CELL = Font(name="微软雅黑", size=9, color=C["text"])
F_SMALL = Font(name="微软雅黑", size=8, color=C["sub"])


def est_lines(text, units):
    n = 0
    for line in text.split("\n"):
        u = sum(2 if ord(ch) > 0x2E80 else 1 for ch in line)
        n += max(1, -(-u // max(1, units)))
    return n


def doc_meta(md_dir):
    meta = {}
    for fn in sorted(os.listdir(md_dir)):
        if not fn.lower().endswith(".md"):
            continue
        try:
            raw = open(os.path.join(md_dir, fn), "rb").read()
        except Exception:
            continue
        txt = None
        for enc in ENCODINGS:
            try:
                txt = raw.decode(enc); break
            except Exception:
                continue
        if txt is None:
            continue
        lines = txt.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else fn
        m = re.search(r"(20\d{2})[-年/\.](\d{1,2})[-月/\.](\d{1,2})", txt)
        date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
        meta[fn] = {"file": fn, "title": title, "date": date}
    return meta


def style_row(ws, row, ncol, band):
    for j in range(1, ncol + 1):
        cell = ws.cell(row=row, column=j)
        cell.border = B_ALL
        cell.fill = PatternFill("solid", fgColor=band)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="知识库关键词体系")
    ap.add_argument("--subtitle", default="")
    a = ap.parse_args()

    merged = json.load(open(a.merged, encoding="utf-8"))
    meta = doc_meta(a.md)
    ndim = len(merged)
    ncol = max(len(d["parents"]) for d in merged)
    parents = []
    for dim in merged:
        for i, p in enumerate(dim["parents"], 1):
            parents.append((dim["dim"], dim["dimName"], f'{dim["dim"]}-{i:02d}', p["parent"], p["subs"]))
    total_subs = sum(len(x[4]) for x in parents)

    wb = Workbook()

    # ---------------------------------------------------------------- ① 总览矩阵
    s1 = wb.active
    s1.title = "① 总览矩阵"
    s1.sheet_view.showGridLines = False
    LAST = get_column_letter(1 + ncol)
    ROW0 = 4
    s1.merge_cells(f"A1:{LAST}1")
    c = s1["A1"]
    c.value = f"{a.title} · 总览（{ndim} 维度 × {ncol} 关键词 = {ndim*ncol}；展开子关键词 {total_subs} 条）"
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center", wrap_text=True); s1.row_dimensions[1].height = 30
    s1.merge_cells(f"A2:{LAST}2")
    c = s1["A2"]; c.value = a.subtitle
    c.font = F_SUB; c.fill = PatternFill("solid", fgColor=C["band"])
    c.alignment = Alignment("center", "center", wrap_text=True); s1.row_dimensions[2].height = 18
    for j, h in enumerate(["技能维度 \\ 关键词"] + [f"关键词{i}" for i in range(1, ncol + 1)], 1):
        cell = s1.cell(row=3, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s1.row_dimensions[3].height = 20
    for r, dim in enumerate(merged):
        row = ROW0 + r
        dm = s1.cell(row=row, column=1, value=f'{dim["dim"]}\n{dim["dimName"]}')
        dm.font = F_DIM; dm.fill = PatternFill("solid", fgColor=C["dim_bg"])
        dm.alignment = Alignment("center", "center", wrap_text=True); dm.border = B_ALL
        for k, p in enumerate(dim["parents"]):
            cell = s1.cell(row=row, column=2 + k, value=p["parent"])
            cell.font = F_CELL
            cell.alignment = Alignment("center", "center", wrap_text=True)
        style_row(s1, row, 1 + ncol, C["band"] if r % 2 else C["white"])
        s1.cell(row=row, column=1).fill = PatternFill("solid", fgColor=C["dim_bg"])
        s1.row_dimensions[row].height = 30
    s1.column_dimensions["A"].width = 16
    for j in range(2, ncol + 2):
        s1.column_dimensions[get_column_letter(j)].width = 14
    s1.print_area = f"A1:{LAST}{ROW0 + ndim - 1}"
    s1.page_setup.orientation = "landscape"
    s1.page_setup.paperSize = s1.PAPERSIZE_A4
    s1.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    s1.page_setup.fitToWidth = 1; s1.page_setup.fitToHeight = 1
    s1.page_margins = PageMargins(0.28, 0.28, 0.35, 0.35, 0.15, 0.15)
    s1.print_options.horizontalCentered = True
    s1.freeze_panes = "B4"

    # ------------------------------------------------- ①B 总览（含子关键词，富文本）
    try:
        from openpyxl.cell.rich_text import CellRichText, TextBlock
        from openpyxl.cell.text import InlineFont
        HAS_RT = True
    except Exception:
        HAS_RT = False
    s1b = wb.create_sheet("①B 总览(含子关键词)", 1)
    s1b.sheet_view.showGridLines = False
    COLW = 15
    s1b.merge_cells(f"A1:{LAST}1")
    c = s1b["A1"]; c.value = f"{a.title} · 总览（含子关键词）"
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center", wrap_text=True); s1b.row_dimensions[1].height = 30
    s1b.merge_cells(f"A2:{LAST}2")
    c = s1b["A2"]; c.value = a.subtitle
    c.font = F_SUB; c.fill = PatternFill("solid", fgColor=C["band"])
    c.alignment = Alignment("center", "center", wrap_text=True); s1b.row_dimensions[2].height = 18
    for j, h in enumerate(["技能维度 \\ 关键词"] + [f"关键词{i}" for i in range(1, ncol + 1)], 1):
        cell = s1b.cell(row=3, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s1b.row_dimensions[3].height = 20
    for r, dim in enumerate(merged):
        row = ROW0 + r
        dm = s1b.cell(row=row, column=1, value=f'{dim["dim"]}\n{dim["dimName"]}')
        dm.font = F_DIM; dm.fill = PatternFill("solid", fgColor=C["dim_bg"])
        dm.alignment = Alignment("center", "center", wrap_text=True); dm.border = B_ALL
        mx = 2
        for k, p in enumerate(dim["parents"]):
            kws = [s["kw"] for s in p["subs"]]
            cell = s1b.cell(row=row, column=2 + k)
            if HAS_RT:
                rt = CellRichText()
                rt.append(TextBlock(InlineFont(rFont="微软雅黑", sz=9, b=True), p["parent"]))
                for i, kw in enumerate(kws):
                    rt.append(TextBlock(InlineFont(rFont="微软雅黑", sz=8), f"\n{i+1}. {kw}"))
                cell.value = rt
            else:
                cell.value = p["parent"] + "\n" + "\n".join(f"{i+1}. {k2}" for i, k2 in enumerate(kws))
            cell.alignment = Alignment("left", "top", wrap_text=True)
            mx = max(mx, est_lines(p["parent"] + "\n" + "\n".join(kws), COLW - 1))
        style_row(s1b, row, 1 + ncol, C["band"] if r % 2 else C["white"])
        s1b.cell(row=row, column=1).fill = PatternFill("solid", fgColor=C["dim_bg"])
        s1b.row_dimensions[row].height = mx * 11.6 + 6
    s1b.column_dimensions["A"].width = 16
    for j in range(2, ncol + 2):
        s1b.column_dimensions[get_column_letter(j)].width = COLW
    s1b.print_area = f"A1:{LAST}{ROW0 + ndim - 1}"
    s1b.page_setup.orientation = "landscape"
    s1b.page_setup.paperSize = s1b.PAPERSIZE_A4
    s1b.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    s1b.page_setup.fitToWidth = 1; s1b.page_setup.fitToHeight = 0
    s1b.page_margins = PageMargins(0.28, 0.28, 0.3, 0.3, 0.15, 0.15)
    s1b.print_options.horizontalCentered = True
    s1b.print_title_rows = "1:3"
    s1b.freeze_panes = "B4"

    # ---------------------------------------------------------------- ② 关键词展开
    s2 = wb.create_sheet("② 关键词展开")
    s2.sheet_view.showGridLines = False
    H2 = ["编号", "技能维度", "父关键词", "子项数", "子关键词（格内换行）", "主要来源文档"]
    s2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(H2))
    c = s2.cell(row=1, column=1, value=f"② 关键词展开 —— 每个父关键词一行（共 {len(parents)} 行）")
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center"); s2.row_dimensions[1].height = 26
    for j, h in enumerate(H2, 1):
        cell = s2.cell(row=2, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s2.row_dimensions[2].height = 26
    r = 3
    for code, dimname, pid, parent, subs in parents:
        kws = [s["kw"] for s in subs]
        srcs = []
        for s in subs:
            if s["src"] not in srcs:
                srcs.append(s["src"])
        for j, v in enumerate([pid, dimname, parent, len(kws),
                               "\n".join(f"{i+1}. {k}" for i, k in enumerate(kws)),
                               "\n".join(srcs)], 1):
            cell = s2.cell(row=r, column=j, value=v)
            cell.font = F_DIM if j == 3 else (F_SMALL if j == 6 else F_CELL)
        style_row(s2, r, len(H2), C["band"] if r % 2 else C["white"])
        for j in range(1, len(H2) + 1):
            s2.cell(row=r, column=j).alignment = (
                Alignment("center", "center") if j in (1, 4)
                else Alignment("left", "top", wrap_text=True))
        s2.row_dimensions[r].height = 15 + 13 * max(len(kws), len(srcs))
        r += 1
    for col, w in zip("ABCDEF", [10, 17, 18, 8, 44, 46]):
        s2.column_dimensions[col].width = w
    s2.freeze_panes = "A3"; s2.auto_filter.ref = f"A2:F{r-1}"; s2.print_title_rows = "1:2"

    # -------------------------------------------------------------- ③ 子关键词明细
    s3 = wb.create_sheet("③ 子关键词明细")
    s3.sheet_view.showGridLines = False
    H3 = ["序号", "编号", "技能维度", "父关键词", "子关键词", "关键点说明", "来源 md 文档", "文档日期"]
    s3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(H3))
    c = s3.cell(row=1, column=1, value=f"③ 子关键词明细 —— 每条一行（共 {total_subs} 条），可按维度/关键词/来源筛选")
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center"); s3.row_dimensions[1].height = 26
    for j, h in enumerate(H3, 1):
        cell = s3.cell(row=2, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s3.row_dimensions[2].height = 22
    r, n = 3, 0
    for code, dimname, pid, parent, subs in parents:
        for s in subs:
            n += 1
            vals = [n, pid, dimname, parent, s["kw"], s.get("note", ""), s["src"],
                    meta.get(s["src"], {}).get("date", "")]
            for j, v in enumerate(vals, 1):
                cell = s3.cell(row=r, column=j, value=v)
                cell.font = F_SMALL if j == 7 else F_CELL
            style_row(s3, r, len(H3), C["band"] if r % 2 else C["white"])
            for j in range(1, len(H3) + 1):
                s3.cell(row=r, column=j).alignment = (
                    Alignment("center", "center") if j in (1, 2, 8)
                    else Alignment("left", "center", wrap_text=True))
            r += 1
    for col, w in zip("ABCDEFGH", [6, 9, 17, 18, 22, 30, 46, 11]):
        s3.column_dimensions[col].width = w
    s3.freeze_panes = "A3"; s3.auto_filter.ref = f"A2:H{r-1}"; s3.print_title_rows = "1:2"
    s3.page_setup.orientation = "landscape"
    s3.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    s3.page_setup.fitToWidth = 1; s3.page_setup.fitToHeight = 0

    # -------------------------------------------------------------- ④ 文档溯源索引
    d2d, d2p, d2s = {}, {}, {}
    for code, dimname, pid, parent, subs in parents:
        for s in subs:
            f = s["src"]
            d2d.setdefault(f, []) ; d2p.setdefault(f, [])
            if dimname not in d2d[f]:
                d2d[f].append(dimname)
            if pid not in d2p[f]:
                d2p[f].append(pid)
            d2s[f] = d2s.get(f, 0) + 1
    cited = len(d2s)
    s4 = wb.create_sheet("④ 文档溯源索引")
    s4.sheet_view.showGridLines = False
    H4 = ["序号", "md 文件名", "文档标题", "日期", "支撑子关键词数", "命中技能维度", "支撑关键词编号"]
    s4.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(H4))
    c = s4.cell(row=1, column=1,
                value=f"④ 文档溯源索引 —— 全部 {len(meta)} 篇逐篇列出（其中 {cited} 篇被引为证据），按支撑数降序")
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center"); s4.row_dimensions[1].height = 26
    for j, h in enumerate(H4, 1):
        cell = s4.cell(row=2, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s4.row_dimensions[2].height = 22
    r = 3
    for i, f in enumerate(sorted(meta, key=lambda x: (-d2s.get(x, 0), meta[x].get("date", ""), x)), 1):
        cnt = d2s.get(f, 0)
        vals = [i, f, meta[f].get("title", ""), meta[f].get("date", ""), cnt,
                "、".join(d2d.get(f, [])) or "—", "、".join(sorted(d2p.get(f, []))) or "—"]
        for j, v in enumerate(vals, 1):
            cell = s4.cell(row=r, column=j, value=v)
            cell.font = F_SMALL if j == 2 else F_CELL
        if cnt == 0:
            style_row(s4, r, len(H4), C["white"])
            for j in (2, 3, 6, 7):
                s4.cell(row=r, column=j).font = Font(name="微软雅黑", size=8, color=C["grey"])
        else:
            style_row(s4, r, len(H4), C["band"] if r % 2 else C["white"])
        for j in range(1, len(H4) + 1):
            s4.cell(row=r, column=j).alignment = (
                Alignment("center", "center") if j in (1, 4, 5)
                else Alignment("left", "center", wrap_text=True))
        r += 1
    for col, w in zip("ABCDEFG", [6, 50, 34, 11, 13, 30, 34]):
        s4.column_dimensions[col].width = w
    s4.freeze_panes = "A3"; s4.auto_filter.ref = f"A2:G{r-1}"; s4.print_title_rows = "1:2"
    s4.page_setup.orientation = "landscape"
    s4.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    s4.page_setup.fitToWidth = 1; s4.page_setup.fitToHeight = 0

    # ---------------------------------------------------------------- ⑤ 维度统计
    s5 = wb.create_sheet("⑤ 维度统计")
    s5.sheet_view.showGridLines = False
    H5 = ["编号", "技能维度", "父关键词数", "子关键词数", "平均子项", "引用文档数", "占子关键词比"]
    s5.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(H5))
    c = s5.cell(row=1, column=1, value="⑤ 维度统计")
    c.font = F_TITLE; c.fill = PatternFill("solid", fgColor=C["title_bg"])
    c.alignment = Alignment("center", "center"); s5.row_dimensions[1].height = 26
    for j, h in enumerate(H5, 1):
        cell = s5.cell(row=2, column=j, value=h)
        cell.font = F_HEAD; cell.fill = PatternFill("solid", fgColor=C["head_bg"])
        cell.alignment = Alignment("center", "center", wrap_text=True); cell.border = B_ALL
    s5.row_dimensions[2].height = 22
    DS = 3
    # 说明：这里直接写计算结果而不是公式 —— 多数预览器不会重算公式，公式格会显示空白
    for i, dim in enumerate(merged):
        row = DS + i
        cnt = sum(len(p["subs"]) for p in dim["parents"])
        docs = {s["src"] for p in dim["parents"] for s in p["subs"]}
        for j, v in enumerate([dim["dim"], dim["dimName"], len(dim["parents"]), cnt,
                               round(cnt / max(1, len(dim["parents"])), 1), len(docs),
                               (cnt / total_subs if total_subs else 0)], 1):
            s5.cell(row=row, column=j, value=v)
        style_row(s5, row, len(H5), C["band"] if row % 2 else C["white"])
        for j in range(1, len(H5) + 1):
            s5.cell(row=row, column=j).alignment = Alignment("center" if j != 2 else "left", "center")
        s5.cell(row=row, column=5).number_format = "0.0"
        s5.cell(row=row, column=7).number_format = "0.0%"
    TOT = DS + ndim
    for j, v in enumerate(["", "合计", sum(len(d["parents"]) for d in merged), total_subs,
                           round(total_subs / max(1, sum(len(d["parents"]) for d in merged)), 1),
                           cited, 1.0], 1):
        s5.cell(row=TOT, column=j, value=v).font = F_DIM
    style_row(s5, TOT, len(H5), C["dim_bg"])
    s5.cell(row=TOT, column=5).number_format = "0.0"
    s5.cell(row=TOT, column=7).number_format = "0.0%"
    for col, w in zip("ABCDEFG", [9, 24, 12, 12, 10, 12, 12]):
        s5.column_dimensions[col].width = w
    ch = BarChart(); ch.type = "col"; ch.style = 10
    ch.title = "各维度子关键词数量"; ch.y_axis.title = "子关键词数"
    ch.add_data(Reference(s5, min_col=4, min_row=2, max_row=DS + ndim - 1), titles_from_data=True)
    ch.set_categories(Reference(s5, min_col=2, min_row=DS, max_row=DS + ndim - 1))
    ch.height, ch.width = 8, 18
    s5.add_chart(ch, "A" + str(TOT + 2))
    s5.freeze_panes = "A3"

    wb.properties.title = a.title
    try:
        wb.save(a.out)
    except PermissionError:
        base, ext = os.path.splitext(a.out)
        a.out = base + "_v2" + ext
        wb.save(a.out)
        print("[注意] 目标文件被占用，已另存为", a.out)
    print("[完成]", a.out)
    print("[信息] 视图：", wb.sheetnames)
    print(f"[信息] 维度={ndim} 父关键词={len(parents)} 子关键词={total_subs} 引用文档={cited}/{len(meta)}")


if __name__ == "__main__":
    main()
