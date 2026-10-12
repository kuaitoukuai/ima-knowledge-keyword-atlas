#!/usr/bin/env bash
# 02_fetch_docs.sh —— 把清单里每一条的正文（Markdown）下载到本地
#
# 用法：
#   bash 02_fetch_docs.sh "<清单 jsonl>" "<输出目录>" [并发数=3]
#
# 关键经验：
#   - 并发过高会被服务端限流，get_media_info 返回空 URL（表现为 NOURL）。
#     实测并发 8 时 510 篇里 242 篇失败；并发 3 + 每篇 4 次重试可 100% 成功。
#   - 已存在且非空的文件会跳过，可安全重复执行（断点续传）。

set -u

LIST="${1:?用法: 02_fetch_docs.sh <清单 jsonl> <输出目录> [并发数]}"
OUTDIR="${2:?请提供输出目录}"
PAR="${3:-3}"

HOME_DIR="${HOME:-$USERPROFILE}"
IMA_SKILL_DIR="${IMA_SKILL_DIR:-$HOME_DIR/.workbuddy/skills/ima-skills}"
API="$IMA_SKILL_DIR/ima_api.cjs"

[ -f "$API" ] || { echo "[错误] 找不到 $API" >&2; exit 1; }
mkdir -p "$OUTDIR"

TMP_JOBS="$(dirname "$OUTDIR")/_jobs.tsv"
TMP_ONE="$(dirname "$OUTDIR")/_one.sh"
LOG="$(dirname "$OUTDIR")/_fetch_log.txt"

node -e '
const fs=require("fs");
const lines=fs.readFileSync(process.argv[1],"utf8").trim().split("\n").filter(Boolean);
const out=[];
lines.forEach((l,i)=>{try{
  const j=JSON.parse(l);
  const safe=(j.title||("doc"+i)).replace(/[\/\\:*?"<>|]/g,"_").replace(/[\r\n]/g,"");
  out.push([String(i+1).padStart(3,"0"), j.media_id, safe].join("\t"));
}catch(e){}});
fs.writeFileSync(process.argv[2], out.join("\n")+"\n");
console.error("[信息] 待下载：" + out.length + " 篇");
' "$LIST" "$TMP_JOBS"

cat > "$TMP_ONE" <<'EOS'
#!/usr/bin/env bash
idx="$1"; mid="$2"; safe="$3"
HOME_DIR="${HOME:-$USERPROFILE}"
IMA_SKILL_DIR="${IMA_SKILL_DIR:-$HOME_DIR/.workbuddy/skills/ima-skills}"
API="$IMA_SKILL_DIR/ima_api.cjs"
OUTDIR="$4"; LOG="$5"
dest="$OUTDIR/$(printf '%s_%s' "$idx" "$safe")"
[ -s "$dest" ] && exit 0
for try in 1 2 3 4; do
  url=$(node "$API" "openapi/wiki/v1/get_media_info" \
      "$(printf '{"media_id":"%s"}' "$mid")" 2>/dev/null \
    | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{const j=JSON.parse(s);process.stdout.write((j.data&&j.data.url_info&&j.data.url_info.url)||"")}catch(e){}})')
  if [ -n "$url" ]; then
    curl -sL --max-time 90 "$url" -o "$dest"
    [ -s "$dest" ] && { echo -e "OK\t$idx\t$safe" >> "$LOG"; exit 0; }
  fi
  sleep $((try * 2))
done
echo -e "FAIL\t$idx\t$safe" >> "$LOG"
EOS
chmod +x "$TMP_ONE"

: > "$LOG"
cat "$TMP_JOBS" | xargs -d '\n' -P "$PAR" -I{} bash -c \
  'IFS=$'"'"'\t'"'"' read -r a b c <<< "$1"; bash "'"$TMP_ONE"'" "$a" "$b" "$c" "'"$OUTDIR"'" "'"$LOG"'"' _ {}

echo "[信息] 目录文件数：$(ls "$OUTDIR" | wc -l | tr -d ' ')"
echo "[信息] 失败：$(grep -c FAIL "$LOG" 2>/dev/null || echo 0) 篇（可重跑本脚本补齐）"
