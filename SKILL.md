---
name: ima-knowledge-keyword-atlas
description: 把 IMA（艾玛）知识库里的成百上千篇 Markdown 笔记，做成一套「分层关键词体系 + 多视图可打印 Excel」的完整流水线。当用户说要「从 ima / 知识库 / 笔记库里提取关键词」「把知识库内容整理成关键词表或关键词体系」「读完全部笔记再总结成 Excel」「做一张 10×10 的关键词总览表」「关键词要能溯源到具体哪一篇笔记」时使用。覆盖：全量拉取笔记 → 建结构索引 → 定维度 → 并行细读展开子关键词 → 硬校验溯源 → 渲染 6 视图 Excel（总览矩阵／含子关键词总览／关键词展开／子关键词明细／文档溯源索引／维度统计）。也适用于其他「批量文档 → 分层关键词 → Excel」的场景。
agent_created: true
---

# IMA 知识库关键词图谱（Keyword Atlas）

把「几百篇散乱笔记」变成「一套可读、可查、可打印、**每条都能追到原文**的关键词体系」。

核心原则：**先结构化，再校验，最后才出表**。中间产物（索引 / 摘要 / 展开 JSON）必须落盘，因为它们是可校验、可重跑的。

---

## 前置条件

| 依赖 | 说明 |
|---|---|
| `ima-skill` | 提供 `ima_api.cjs`（接口封装）与 IMA 凭证。脚本默认从 `~/.workbuddy/skills/ima-skills` 找，可用环境变量 `IMA_SKILL_DIR` 覆盖 |
| IMA 凭证 | `~/.config/ima/{client_id,api_key}` 或环境变量 `IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY` |
| `node` | 在 PATH 中（接口调用用） |
| `python3` + `openpyxl≥3.1` | 建索引与生成 Excel（脚本会自动装 openpyxl） |

---

## 六阶段流程

> 详细说明、完整命令、子代理提示词模板 → 读 `references/workflow.md` 与 `references/subagent-prompt.md`。

**先做一件事：跟用户确认「视角」。** 同一批笔记，按「项目」分和按「个人技术技能」分会得出完全不同的体系，
这是最容易整表返工的地方。确认视角后再往下走。

| 阶段 | 做什么 | 命令 / 产出 |
|---|---|---|
| **A 拉取** | 翻页拉全量清单，再把每篇正文下载到本地 | `01_list_kb.sh` → `list.jsonl`；`02_fetch_docs.sh` → `md/` |
| **B 建索引 + 定维度** | 把每篇压成「标题/日期/小标题/要点原句/强调词」；读 `pack_*.md` 通读全量，产出 `taxonomy.json` | `03_index_docs.py` → `index/`；再确定维度数 × 每维关键词数 |
| **C 聚类出摘要** | 按维度把命中文档聚起来，每维度出「完整版 + 紧凑版」 | `04_cluster_digest.py` → `digest/`、`digest/c/` |
| **D 并行细读** | 每 1~2 个维度派一个子代理，把每个父关键词展开成 3~7 个子关键词并标注来源 | 提示词模板见 `references/subagent-prompt.md` → `expand/*.json` |
| **E 合并校验** | 校验父关键词集合一致、子项数在区间、**每条 src 真实存在** | `05_merge_validate.py` → `merged.json` |
| **F 出表** | 渲染 6 个视图的 Excel | `06_build_workbook.py` → `关键词体系.xlsx` |

一次跑完（假设工作目录为 `$WD`）：

```bash
SD="<本 skill 的 scripts 绝对路径>"

bash    "$SD/01_list_kb.sh"   "<知识库名称>"              "$WD/list.jsonl"
bash    "$SD/02_fetch_docs.sh" "$WD/list.jsonl"            "$WD/md" 3
python3 "$SD/03_index_docs.py"    --src "$WD/md" --out "$WD/index" --per-pack 40
#   ← 此处读 $WD/index/pack_*.md，写出 $WD/taxonomy.json
python3 "$SD/04_cluster_digest.py" --index "$WD/index/index.json" \
        --taxonomy "$WD/taxonomy.json" --out "$WD/digest" --top 32
#   ← 此处并行派子代理，产出 $WD/expand/*.json
python3 "$SD/05_merge_validate.py" --expand "$WD/expand" \
        --taxonomy "$WD/taxonomy.json" --md "$WD/md" --out "$WD/merged.json"
python3 "$SD/06_build_workbook.py" --merged "$WD/merged.json" --md "$WD/md" \
        --out "$WD/关键词体系.xlsx" --title "<标题>" --subtitle "<统计区间｜来源｜口径>"
```

---

## 四条必须守住的约束

1. **下载并发 ≤ 3。** 并发 8 时实测 510 篇有 242 篇被限流。必须低并发 + 重试（脚本已内置，可反复重跑补齐）。
2. **Phase E 不可跳过。** 子代理最容易犯两个错：**编造来源文件名**、**父关键词少一个/多一个**。
   校验脚本会直接报错退出——修正后重跑，不要带着错误建表。
3. **子关键词必须能溯源。** 每条 `src` 都要是 `md/` 下真实文件名。宁可让同一父关键词的多个子项引用同一篇权威文档，也不要硬拆到弱相关文档上。
4. **静态速览表不要写 Excel 公式。** openpyxl 写的公式没有缓存值，pandas / `data_only=True` / 多数在线预览器都会显示**空白**。先在 Python 里算好结果写死。

## 出表后的自检清单

- 总览矩阵格子数 == 维度数 × 每维关键词数，无空格
- 明细行数 == 子关键词总数；溯源表行数 == `md/` 文件数
- 富文本抽查：`load_workbook(f, rich_text=True)` → 父关键词段 `font.b == True`
- 一页纸视图 `fitToWidth=1, fitToHeight=1`；内容多的视图 `fitToHeight=0` 让它续页，**并把页数如实告诉用户**，不要假装一页装得下
- 目标 xlsx 若正被打开，`wb.save()` 会 `PermissionError` → 脚本会自动另存 `_v2.xlsx`，需告知用户

---

## 资源清单

```
ima-knowledge-keyword-atlas/
├── SKILL.md
├── scripts/
│   ├── 01_list_kb.sh           翻页拉取知识库条目清单 → JSONL
│   ├── 02_fetch_docs.sh        按清单下载全部 Markdown（低并发+重试+断点续传）
│   ├── 03_index_docs.py        抽取标题/小标题/要点原句/强调词 → index.json + 可读索引包
│   ├── 04_cluster_digest.py    按 taxonomy 聚类 → 每维度完整摘要 + 紧凑摘要
│   ├── 05_merge_validate.py    合并子代理结果并硬校验（父关键词集合 / 子项数 / src 存在性）
│   └── 06_build_workbook.py    渲染 6 视图 Excel
├── references/
│   ├── workflow.md             六阶段完整说明 + 规模基准 + 交付自检清单
│   ├── subagent-prompt.md      Phase D 子代理提示词模板（可直接复制）
│   ├── ima-api-notes.md        IMA 接口速查 + 8 条踩坑（EBUSY / 限流 / 编码 / 重名）
│   └── excel-patterns.md       Excel 6 视图设计 + 富文本/行高/打印/公式/占用 等技巧
└── assets/
    └── taxonomy.example.json   taxonomy.json 结构示例
```

---

## 规模与耗时基准（实测）

| 项 | 数值 |
|---|---|
| 源文档 | 510 篇 md，约 6.3 MB |
| 维度 / 父关键词 / 子关键词 | 10 / 100 / 579 |
| 被引用文档 | 121 篇（其余为同内容副本或非证据文档） |
| 端到端 | 下载约 12 min（含重试），其余阶段约 10 min |

---

## 调整口子

用户改需求时，通常只需要动这几处，不用重跑全流程：

| 想改什么 | 改哪里 | 是否重跑 |
|---|---|---|
| 关键词措辞、增删关键词 | `taxonomy.json` 的 `parents` | 需重跑 D~F |
| 维度数量 / 每维关键词数（如 8×6） | `taxonomy.json` 的维度定义 | 需重跑 D~F |
| 只改子关键词 | 直接改 `expand/*.json` 或 `merged.json` | 只需 E~F |
| 只改 Excel 样式/视图 | `06_build_workbook.py` | 只需 F |
| 换一个知识库 | — | 全量 A~F |
