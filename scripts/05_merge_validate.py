#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
05_merge_validate.py —— 合并各维度的展开结果并做硬校验

子代理产出（每个文件 1~2 个维度）放在 <expand 目录>/*.json，结构：
{
  "dimensions": [
    {"dim": "D01", "dimName": "编程与代码基本功",
     "parents": [
       {"parent": "参数名格式一致",
        "subs": [{"kw": "price 而非 product_price", "note": "参数命名踩坑", "src": "123_xxx.md"}]}
     ]}
  ]
}

校验项（任一不过就报错退出）：
  1. 每个维度的父关键词集合 == taxonomy 里定义的集合（不重不漏）
  2. 每个父关键词的子关键词数在 [min_subs, max_subs] 之间
  3. 每条 src 都真实存在于 <md 目录>（杜绝编造来源）
输出 merged.json（供 06 建表）与校验报告。

用法：
  python3 05_merge_validate.py --expand <展开目录> --taxonomy <taxonomy.json> \
      --md <md目录> --out <merged.json> [--min-subs 3] [--max-subs 7]
"""
import argparse, glob, json, os, sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expand", required=True)
    ap.add_argument("--taxonomy", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-subs", type=int, default=3)
    ap.add_argument("--max-subs", type=int, default=7)
    a = ap.parse_args()

    tax = json.load(open(a.taxonomy, encoding="utf-8"))
    expect = {d["dim"]: list(d.get("parents", [])) for d in tax["dimensions"]}
    real = set(os.listdir(a.md))

    merged, problems, bad_src, total = [], [], [], 0
    for fp in sorted(glob.glob(os.path.join(a.expand, "*.json"))):
        data = json.load(open(fp, encoding="utf-8"))
        for dim in data.get("dimensions", []):
            code = dim["dim"]
            got = [p["parent"] for p in dim.get("parents", [])]
            exp = expect.get(code, [])
            if exp:
                miss = [x for x in exp if x not in got]
                extra = [x for x in got if x not in exp]
                if miss or extra:
                    problems.append(f"{code} 父关键词不一致：缺={miss} 多={extra}")
            for p in dim.get("parents", []):
                subs = p.get("subs", [])
                total += len(subs)
                if not (a.min_subs <= len(subs) <= a.max_subs):
                    problems.append(f"{code}/{p['parent']} 子关键词数={len(subs)}（应在 {a.min_subs}~{a.max_subs}）")
                for s in subs:
                    if s.get("src") not in real:
                        bad_src.append(f"{code}/{p['parent']}/{s.get('kw')} -> {s.get('src')}")
            merged.append(dict(dim=code, dimName=dim["dimName"], parents=dim.get("parents", [])))

    json.dump(merged, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"[结果] 维度={len(merged)}  父关键词={sum(len(m['parents']) for m in merged)}  子关键词={total}")
    print(f"[结果] 结构问题：{'无' if not problems else len(problems)}")
    for p in problems[:20]:
        print("   -", p)
    print(f"[结果] 不存在的来源文件：{len(bad_src)}")
    for b in bad_src[:20]:
        print("   -", b)

    if problems or bad_src:
        print("[失败] 存在问题，请修正后重跑（不要带着错误建表）", file=sys.stderr)
        sys.exit(1)
    print("[完成] 校验通过 ->", a.out)


if __name__ == "__main__":
    main()
