#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
04_cluster_digest.py —— 按维度聚类，产出「逐维度精读摘要」

输入：03 生成的 index.json + taxonomy.json（维度定义）
输出：
  <out>/D01.md …          全量命中清单（每篇：标题/日期/小标题/要点原句）
  <out>/c/D01.md …        紧凑版（每维度取相关度前 N 篇，供直接读进上下文）

taxonomy.json 结构（维度名与匹配词由模型在 Phase B 定稿）：
{
  "dimensions": [
    {"dim": "D01", "dimName": "编程与代码基本功",
     "match": ["语法", "异常", "编码", "正则", "..."],
     "parents": ["参数名格式一致", "..."]}
  ]
}

用法：
  python3 04_cluster_digest.py --index <index.json> --taxonomy <taxonomy.json> \
      --out <摘要目录> [--top 32] [--max-struct 7] [--max-key 5] [--trunc 78]
"""
import argparse, io, json, os


def blob(d):
    return " ".join([d.get("title", ""), " ".join(d.get("heads", [])),
                     " ".join(d.get("bolds", [])), " ".join(d.get("keys", []))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--top", type=int, default=32)
    ap.add_argument("--max-struct", type=int, default=7)
    ap.add_argument("--max-key", type=int, default=5)
    ap.add_argument("--trunc", type=int, default=78)
    ap.add_argument("--min-hits", type=int, default=8,
                    help="命中篇数低于此值即告警（通常是 match 词太窄或误填成了 parents）")
    a = ap.parse_args()

    docs = json.load(open(a.index, encoding="utf-8"))
    tax = json.load(open(a.taxonomy, encoding="utf-8"))
    os.makedirs(os.path.join(a.out, "c"), exist_ok=True)

    print(f"[信息] 共 {len(docs)} 篇文档，{len(tax['dimensions'])} 个维度")
    warned = []
    for dim in tax["dimensions"]:
        code, name, kws = dim["dim"], dim["dimName"], dim.get("match", [])
        scored = []
        for d in docs:
            b = blob(d)
            hit = sum(1 for k in kws if k in b)
            if hit:
                scored.append((hit, d))
        # 命中数降序；同分按文件名，保证可复现
        scored.sort(key=lambda x: (-x[0], x[1]["file"]))

        full = io.StringIO()
        full.write(f"# {code} {name} —— 命中 {len(scored)} 篇\n\n")
        for hit, d in scored:
            full.write(f"## [{d['file']}] {d['title']}\n- 相关度：{hit} ｜ 日期：{d['date']}\n")
            if d["heads"]:
                full.write("- 结构：" + " ｜ ".join(d["heads"][:16]) + "\n")
            if d["bolds"]:
                full.write("- 强调：" + "、".join(d["bolds"][:12]) + "\n")
            for k in d["keys"][:8]:
                full.write(f"  - {k}\n")
            full.write("\n")
        open(os.path.join(a.out, f"{code}.md"), "w", encoding="utf-8").write(full.getvalue())

        cond = io.StringIO()
        cond.write(f"# {code} {name}（命中 {len(scored)} 篇，取相关度前 {min(a.top, len(scored))} 篇）\n\n")
        for hit, d in scored[:a.top]:
            cond.write(f"[{d['file']}] {d['title']}  <{d['date']} rel={hit}>\n")
            for h in d["heads"][:a.max_struct]:
                cond.write(f"  · {h[:a.trunc]}\n")
            for k in d["keys"][:a.max_key]:
                cond.write(f"  > {k[:a.trunc]}\n")
            cond.write("\n")
        open(os.path.join(a.out, "c", f"{code}.md"), "w", encoding="utf-8").write(cond.getvalue())

        print(f"  {code} {name}: 命中 {len(scored)} 篇，紧凑版取前 {min(a.top, len(scored))} 篇")
        if len(scored) < a.min_hits:
            warned.append((code, name, len(scored)))

    if warned:
        print("\n[告警] 以下维度命中文档过少，请检查 taxonomy 的 match 词是否太窄")
        print("       （常见错误：把 parents 里的展示用关键词直接当成了 match 检索词）")
        for code, name, n in warned:
            print(f"       - {code} {name}：仅命中 {n} 篇")
    print(f"[完成] 摘要输出到 {a.out}（完整版）与 {a.out}/c（紧凑版）")


if __name__ == "__main__":
    main()
