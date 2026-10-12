# IMA 知识库接入要点与踩坑

## 接口速查

| 目的 | 接口 | 关键参数 |
|---|---|---|
| 找知识库 ID | `openapi/wiki/v1/search_knowledge_base` | `query`（空串=列出全部）、`cursor`、`limit` |
| 浏览条目（含翻页） | `openapi/wiki/v1/get_knowledge_list` | `knowledge_base_id`、`cursor`、`limit`(1~50)、可选 `folder_id` |
| 关键词搜索 | `openapi/wiki/v1/search_knowledge` | `query`、`knowledge_base_id`、`cursor` |
| 取正文直链 | `openapi/wiki/v1/get_media_info` | `media_id` |

- 所有请求都是 **POST + JSON body**，发往 `https://ima.qq.com`。
- 响应统一 `{"code":0,"msg":"...","data":{...}}`，`code≠0` 直接把 `msg` 给用户。
- 列表接口用的是 `data.knowledge_list`（**不是** `info_list`；`info_list` 是搜索类接口的字段）。
  `data.is_end` / `data.next_cursor` 控制翻页。

## 调用方式

调用封装在 ima-skill 的 `ima_api.cjs`：

```bash
node "$IMA_SKILL_DIR/ima_api.cjs" "<apiPath>" '<json body>'
```

凭证按 **环境变量 → 配置文件** 顺序读取：
- `IMA_OPENAPI_CLIENTID` / `IMA_OPENAPI_APIKEY`
- 或 `~/.config/ima/client_id` / `~/.config/ima/api_key`

凭证只在 HTTP header 里发往 `ima.qq.com`，不会落到别处。

## 踩坑清单

### 1. 不要在 Node 进程里 `execFileSync` 再调 `node` —— 会 EBUSY

```
Error: spawnSync ... EBUSY
```

Windows 下父 node 进程再 spawn 同名 node 可执行文件会失败。
**对策**：由 bash 循环调用 `node ima_api.cjs ...`，需要解析 JSON 时再单独起一个 `node -e` 进程读 stdin。
（本 skill 的 `01`/`02` 脚本已按此写法。）

### 2. 并发下载会被限流

`get_media_info` 并发 8 时，510 篇里有 **242 篇**返回空 URL（表现为 `NOURL`）。
**对策**：并发降到 **3**，每篇最多重试 4 次、退避 `2s/4s/6s`。实测 100% 成功。

### 3. 用 `\t` 而不是 `|` 做 `cut` 分隔符

把多个字段拼成一行回传给 bash 时，如果用 `|||` 拼接，`cut -d'|' -f3` 会把空字段拆错位。
**对策**：统一用制表符分隔，`IFS=$'\t' read -r a b c`。

### 4. 正文是 Markdown，直链是临时签名 URL

`get_media_info` 返回 `data.url_info.url`，带签名与时效，**必须立刻下载**，不要存起来复用。
`media_type=7` 表示 Markdown；`media_type=11` 是笔记，需要转 notes 模块取内容。

### 5. 外链可强制指定文件名

需要「导出/另存」而不是在线预览时，在直链后追加：

```
response-content-type=application/octet-stream
response-content-disposition=attachment;filename="<想要的文件名>"
```

### 6. 文件名要清洗

条目标题可能含 `/ \ : * ? " < > |` 与换行，直接当文件名会失败。
**对策**：`re.sub(r'[\/\\:*?"<>|]', '_', title)`，再去掉 `\r\n`。

### 7. 文档会大量重复

同一份内容常以不同时间戳后缀存多份（如 `_ai问答.md` / `_20261010164405.md`）。
510 篇里真正独立的主题远少于 510。**统计时按内容去重，但溯源时保留真实文件名。**

### 8. PowerShell 下请求 Body 必须转 UTF-8 字节数组

PowerShell 5.1 的 `Invoke-RestMethod` 会把 body 静默转成 ANSI(GBK)，中文变乱码。
本 skill 用 bash + node 调接口，不受影响；若改用 PowerShell 需显式 `[Text.Encoding]::UTF8.GetBytes()`。
