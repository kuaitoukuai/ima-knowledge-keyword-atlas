#!/usr/bin/env bash
# 01_list_kb.sh —— 拉取 IMA 知识库的完整条目清单（含翻页），输出 JSONL
#
# 用法：
#   bash 01_list_kb.sh "<知识库名称或 kb_id>" "<输出 jsonl 路径>"
#
# 说明：
#   - 参数若是 kb_id（以 = 结尾的长串）则直接使用；否则先用 search_knowledge_base 按名称搜索。
#   - 需要 IMA 凭证：环境变量 IMA_OPENAPI_CLIENTID / IMA_OPENAPI_APIKEY，或 ~/.config/ima/{client_id,api_key}。
#   - 依赖 ima-skill 的 ima_api.cjs，路径可用环境变量 IMA_SKILL_DIR 覆盖。

set -u

KB_ARG="${1:?用法: 01_list_kb.sh <知识库名称或 kb_id> <输出 jsonl>}"
OUT="${2:?请提供输出 jsonl 路径}"

HOME_DIR="${HOME:-$USERPROFILE}"
IMA_SKILL_DIR="${IMA_SKILL_DIR:-$HOME_DIR/.workbuddy/skills/ima-skills}"
API="$IMA_SKILL_DIR/ima_api.cjs"

[ -f "$API" ] || { echo "[错误] 找不到 $API ；请先安装 ima-skill，或设置 IMA_SKILL_DIR" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "[错误] 需要 node 在 PATH 中" >&2; exit 1; }

# 注意：Node 内部用 execFileSync 再调 node 会 EBUSY，所以固定由 bash 调 node。
KB="$KB_ARG"
case "$KB" in
  *=) : ;;                                   # 形如 xxx= ，直接当 kb_id
  *)
    echo "[信息] 按名称搜索知识库：$KB" >&2
    RES=$(node "$API" "openapi/wiki/v1/search_knowledge_base" \
        "$(printf '{"query":"%s","cursor":"","limit":20}' "$KB")" 2>/dev/null)
    KB=$(printf '%s' "$RES" | node -e '
let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
  try{const j=JSON.parse(s);
    const l=(j.data&&j.data.info_list)||[];
    if(!l.length){console.error("[错误] 未搜到知识库");process.exit(1);}
    console.error("[信息] 候选: "+l.map(x=>x.kb_name).join(" | "));
    process.stdout.write(l[0].kb_id);
  }catch(e){console.error("[错误] 解析失败");process.exit(1);}
});')
    [ -n "$KB" ] || exit 1
    ;;
esac
echo "[信息] 知识库 ID: $KB" >&2

: > "$OUT"
cursor=""
for i in $(seq 1 60); do
  body=$(printf '{"knowledge_base_id":"%s","cursor":"%s","limit":50}' "$KB" "$cursor")
  out=$(node "$API" "openapi/wiki/v1/get_knowledge_list" "$body" 2>/dev/null)
  # 用制表符分隔返回值，避免 "|||" 被 cut 拆错
  res=$(printf '%s' "$out" | node -e '
let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
  try{
    const j=JSON.parse(s);
    if(j.code!==0){console.log("0\t1\t");return;}
    const d=j.data||{};const l=d.knowledge_list||[];
    require("fs").appendFileSync(process.argv[1], l.map(x=>JSON.stringify(x)).join("\n")+(l.length?"\n":""));
    console.log(l.length+"\t"+(d.is_end?1:0)+"\t"+(d.next_cursor||""));
  }catch(e){console.log("0\t1\t");}
});' "$OUT")
  n=$(printf '%s' "$res" | cut -f1)
  isend=$(printf '%s' "$res" | cut -f2)
  cursor=$(printf '%s' "$res" | cut -f3)
  echo "[信息] 第 $i 页：$n 条（is_end=$isend）" >&2
  if [ "$isend" = "1" ] || [ "$n" = "0" ]; then break; fi
done

TOTAL=$(wc -l < "$OUT" | tr -d ' ')
echo "$TOTAL"
echo "[完成] 清单已写入 $OUT（共 $TOTAL 条）" >&2
