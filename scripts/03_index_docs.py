#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
03_index_docs.py —— 把成千上万篇 md 压成「可精读的结构索引」

做三件事：
  1. 逐篇抽取：标题、日期、各级小标题、问题/原因/解决/教训类原句、强调词（**…**）
  2. 输出 index.json（全量结构化，供后续聚类/校验/溯源）
  3. 输出 pack_NN.md（每 N 篇一个包，可直接读进上下文，用来通读全量而不爆上下文）

用法：
  python3 03_index_docs.py --src <md目录> --out <索引输出目录> [--per-pack 40]
"""
import argparse, io, json, os, re, sys

KEY_PAT = re.compile(
    r"(问题|原因|根因|解决|修复|坑|教训|铁律|注意|结论|方案|报错|失败|踩|误区|经验|优化|规范|原则|"
    r"必须|禁止|边界|风险|回滚|bug|Bug|BUG)")
HEAD_PAT = re.compile(r"^\s{0,3}(#{1,4})\s+(.+?)\s*$")
BOLD_PAT = re.compile(r"\*\*(.{2,30}?)\*\*")
ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "big5", "latin-1")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u200b", "")).strip()


def read_text(path: str):
    raw = open(path, "rb").read()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return None


def index_one(path: str, fn: str) -> dict:
    txt = read_text(path)
    if txt is None:
        return {}
    lines = txt.splitlines()
    title = clean(lines[0].lstrip("# ")) if lines else fn
    m = re.search(r"(20\d{2})[-年/\.](\d{1,2})[-月/\.](\d{1,2})", txt)
    date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""
    heads, keys, bolds = [], [], []
    for ln in lines:
        s = ln.strip()
        if s.startswith(("|", "---", "```")):      # 表格/分隔线/代码块噪音
            continue
        h = HEAD_PAT.match(ln)
        if h:
            t = clean(h.group(2))
            if t and t != title and t not in heads:
                heads.append(t)
            continue
        t = clean(ln.lstrip("->*• \t"))
        if not t or len(t) < 6:
            continue
        for b in BOLD_PAT.findall(t):
            b = clean(b)
            if 2 <= len(b) <= 20 and b not in bolds:
                bolds.append(b)
        if KEY_PAT.search(t) and len(t) <= 160 and t not in keys:
            keys.append(t)
    return dict(file=fn, title=title, date=date, heads=heads[:22],
                keys=keys[:16], bolds=bolds[:14], chars=len(txt), lines=len(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="md 目录")
    ap.add_argument("--out", required=True, help="索引输出目录")
    ap.add_argument("--per-pack", type=int, default=40)
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    docs = []
    for fn in sorted(os.listdir(a.src)):
        if not fn.lower().endswith(".md"):
            continue
        try:
            d = index_one(os.path.join(a.src, fn), fn)
        except Exception as e:
            print(f"[警告] 跳过 {fn}: {e}", file=sys.stderr)
            continue
        if d:
            docs.append(d)

    json.dump(docs, open(os.path.join(a.out, "index.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    pk = 0
    for i in range(0, len(docs), a.per_pack):
        pk += 1
        buf = io.StringIO()
        buf.write(f"# 文档索引包 {pk}（第 {i+1} ~ {min(i+a.per_pack, len(docs))} 篇，共 {len(docs)} 篇）\n\n")
        for d in docs[i:i + a.per_pack]:
            buf.write(f"## [{d['file']}] {d['title']}\n")
            buf.write(f"- 日期：{d['date']} ｜ 字符数：{d['chars']}\n")
            if d["heads"]:
                buf.write("- 小标题：" + " ｜ ".join(d["heads"]) + "\n")
            if d["bolds"]:
                buf.write("- 强调词：" + "、".join(d["bolds"]) + "\n")
            for k in d["keys"]:
                buf.write(f"  - {k}\n")
            buf.write("\n")
        open(os.path.join(a.out, f"pack_{pk:02d}.md"), "w", encoding="utf-8").write(buf.getvalue())

    print(f"[完成] {len(docs)} 篇 -> index.json + {pk} 个索引包（{a.out}）")


if __name__ == "__main__":
    main()
