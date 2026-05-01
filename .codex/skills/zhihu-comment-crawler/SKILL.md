---
name: zhihu-comment-crawler
description: 立即执行知乎评论爬取任务。用于：用户要求爬知乎评论、知乎评论爬虫、抓知乎评论、导出知乎评论、按关键词抓知乎帖子评论、飞书爬虫、关键词=xxx、主题=xxx，而且目标是实际执行而不是讨论方案。
---

# Zhihu Comment Crawler

这个 skill 的目标不是分析可行性，而是**直接执行**现成的知乎评论抓取器。

## 触发信号

只要用户意图明显属于下面任一类，就立刻启用这个 skill：

- `爬知乎评论`
- `知乎评论爬虫`
- `抓知乎评论`
- `导出知乎评论`
- `按关键词抓知乎评论`
- `飞书爬虫`
- `关键词=家`
- `主题=孩子`

如果用户是在问“能不能做”“怎么做”，可以先简短回答。
但只要用户已经在下达执行命令，就不要退回到方案讨论。

## 绝对规则

1. 不要再回复“当前实例未接入知乎评论爬虫执行器”。
2. 不要重新写爬虫，不要改用浏览器手搓流程，不要先给方案 A/B。
3. 单个关键词时，默认直接执行本机现成脚本：

```bash
python3 /Users/lulu/AIWork/scripts/zhihu_openclaw_executor.py --keyword "<关键词>" --out-root /Users/lulu/.openclaw/workspace/output/openclaw_zhihu_jobs --send-feishu-images
```

如果当前会话上下文里有 `Conversation info (untrusted metadata)` 或 `Sender (untrusted metadata)`，优先提取 `sender_id` / `id` 作为稳定标识传给执行器；如果 OpenClaw 配置里已经维护了 `open_id -> 中文文件夹名` 映射，执行器会自动按中文名建文件夹；如果还能拿到显示名，再一起传：

```bash
--requester-open-id "<open_id>" --requester-name "<显示名>"
```

4. 如果用户一次给了多个关键词，并且它们由 `、`、`，`、`,`、换行分隔，不要自己拆循环，不要改走别的执行路径，一律调用批量执行器：

```bash
python3 /Users/lulu/AIWork/scripts/zhihu_openclaw_batch_executor.py --keyword "<关键词1>" --keyword "<关键词2>" --out-root /Users/lulu/.openclaw/workspace/output/openclaw_zhihu_jobs --send-feishu-images
```

5. 如果用户要求“先试跑”“先少量验证”“先抓前 N 个结果”，映射为：

```bash
python3 /Users/lulu/AIWork/scripts/zhihu_openclaw_executor.py --keyword "<关键词>" --out-root /Users/lulu/.openclaw/workspace/output/openclaw_zhihu_jobs --max-results N --send-feishu-images
```

6. 如果用户明确给了 `storage-state` 路径，再补上：

```bash
--storage-state "/absolute/path/to/state.json"
```

7. 如果用户要求“最近 3 个月 / 最近 N 个月”，直接补：

```bash
--recent-months N
```

8. 如果用户给的是明确起始日期，例如“只要 2026-01-27 之后的评论”，直接补：

```bash
--comment-created-since 2026-01-27
```

9. 成功爬取后，默认交付物固定为：`简版图片 + 详细版图片 + PDF + 原始数据表格`。不要把 HTML 当作飞书主交付入口；HTML/JSON 只作为渲染中间产物或源文件备查。
10. 为了让画像图和结构化画像都能生成，执行爬虫时默认补：

```bash
--out-root /Users/lulu/.openclaw/workspace/output/openclaw_zhihu_jobs --keep-local-output --send-feishu-images
```

11. 画像总结发完后，如果用户没有明确要求保留本地副本，立刻删除该次 `job_dir`，不要把评论原始文件长期留在本机。
    建议直接执行：

```bash
rm -rf "<job_dir>"
```

## 参数提取

从用户自然语言里提取这些字段：

- `keyword`
  - 常见写法：`关键词=家`、`主题=孩子`、`查 家`、`抓 家 的知乎评论`
  - 如果是多个关键词，优先按 `、`、`，`、`,`、换行分隔
- `max_results`
  - 常见写法：`先试 5 个结果`、`先抓前 10 条帖子`
- `recent_months`
  - 常见写法：`最近 3 个月`、`只看最近 6 个月`
- `comment_created_since`
  - 常见写法：`只要 2026-01-27 之后的评论`

如果缺少关键词，只问一句：

`要抓哪个关键词？直接回我“关键词=家”这种格式就行。`

## 执行动作

1. 先提取关键词和可选参数。
2. 立即运行执行脚本。
3. 等脚本返回 JSON 结果。
4. 如果脚本返回 `ok=true` 且存在 `persona_visuals`，优先交付简版图片、详细版图片和 PDF。旧字段里 `overview_dashboard` 视为简版图片，`persona_cards` 视为详细版图片。
5. 如果脚本返回 `persona_brief`，直接用它生成一版**简明画像**，优先覆盖：
   - 一句话总画像
   - 4 类讨论者分布
   - 讨论者最关注的问题
   - 发声目的
   - 高压问题标题
6. 成功时把“原始数据表格 + 简版图片 + 详细版图片 + PDF + 简明画像”一起回给用户：
   - 飞书多维表格链接
   - 简版图片：如果 `persona_visuals.delivery.message_send_ok=true`，写“已直接发送到飞书消息”；否则给简版图片 drive_url
   - 详细版图片：如果 `persona_visuals.delivery.message_send_ok=true`，写“已直接发送到飞书消息”；否则给详细版图片 drive_url
   - PDF：给 PDF drive_url；如果脚本没返回 PDF，先补渲染并上传
   - 如果脚本返回了共享文件夹信息，再附上共享文件夹链接
   - 关键词
   - 抓到的资源数
   - 导出的评论总数
   - 用户画像结论
   - 本地文件已在画像分析后自动清理（默认）
7. 失败时不要泛泛而谈，直接说脚本返回的真实报错，并给最小下一步。
8. 绝对不要编造“我已经改了临时目录 / 换了缓存登录态 / DNS 不通 / 当前实例出不了网”这类过程描述；只有当工具输出里明确出现这些信息时，才能转述。

## 默认交付包

后续爬虫任务默认只主推这 4 类产物：

- `简版图片`: 快速总览，包含样本概览、4 类讨论者分布、最关注的问题、发声目的、高压标题和一句话画像。
- `详细版图片`: 详细画像报告，包含每类画像解释、代表用户/评论样本；若已完成头像视觉分类，必须把头像自我呈现层并入对应用户画像详情。
- `PDF`: 与详细版内容一致或覆盖完整报告，用于飞书直接预览和下载。
- `原始数据表格`: 飞书多维表格或 CSV/XLSX，至少保留原始评论数据；画像流程还应保留评论层标注和用户聚合画像表。

HTML/JSON 可以生成，但只作为内部中间产物。飞书里不要默认让用户点 HTML，因为会按源码预览。长图必须裁掉底部空白后再上传。

画像图默认套用 V3.1 两层模板：简版图使用 hero 标题区、样本统计卡、4 类画像卡、高压/高频话题条形图、`高频情绪词`、`高强度触发词`、`第一层：汇报看板` 和核心判断；详细图在同一视觉体系下增加每类画像的情绪强度/情绪词/触发词，以及 `第二层：详细画像报告`，展开每类用户的需求、表达边界、内容启发、代表评论证据。若已完成头像下载/分类，必须把 A1-A9 头像类型、P1-P6 自我呈现、代表头像样本和方法边界并入对应用户画像详情。不要临时换成海报、普通信息图或纯 Markdown 长图风格，除非用户明确要求改版。

## 画像图输出

执行器默认会返回这些画像图结果：

- `persona_visuals.overview_dashboard.drive_url`
- `persona_visuals.persona_cards.drive_url`
- `persona_visuals.pdf.drive_url`，如果执行器已渲染 PDF
- `persona_visuals.brief_image.drive_url`，如果执行器区分简版图
- `persona_visuals.detail_image.drive_url`，如果执行器区分详细版图
- `persona_visuals.overview_dashboard.image_key`，仅当飞书图片消息上传成功
- `persona_visuals.persona_cards.image_key`，仅当飞书图片消息上传成功
- `persona_visuals.delivery.message_send_ok`
- `persona_visuals.delivery.degraded`
- `persona_visuals.delivery.degrade_reason`
- `persona_brief`

如果 `delivery.message_send_ok=true`，回复里写：

```text
简版图片：已直接发送到飞书消息
详细版图片：已直接发送到飞书消息
```

如果 `delivery.message_send_ok=false`，回复里不要说“已发图”，改给两个 `drive_url`。如果 `delivery.degraded=true`，追加真实降级原因。

若执行器只返回旧字段：

- 把 `overview_dashboard` 视为 `简版图片`。
- 把 `persona_cards` 或详细长图视为 `详细版图片`。
- 若没有 PDF，必须补渲染 PDF 后再作为完整交付；不能只给 HTML。
- 若截图底部有大面积空白，必须裁剪后重新上传。

## 画像分析输入

执行器在 `--keep-local-output` 时会返回这些临时分析文件：

- `analysis_inputs.comment_layer_csv`
- `analysis_inputs.user_profiles_csv`
- `analysis_inputs.summary_json`

优先把这三份文件喂给 `$social-user-profile-universe`。如果其中某一份缺失，再回退读 `comments_json/comments_csv`。

知乎画像的固定要求：

- 按 `Zhihu / 知乎` 路由，不要误用小红书口径。
- 有 `author_avatar_url` 不等于完成头像视觉分类。
- 可以引用“头像链接可供人工点开查看”，但**不要**输出头像风格分布。
- 用低断言措辞，例如“在该议题中更常扮演……”“更倾向于……”。

如果是多个关键词批量执行：

- 对每个关键词各生成一版 4-8 行的简明画像
- 不要把多个关键词硬混成一个画像
- 每个关键词的飞书表格链接和画像结论分别列出

## 成功回复模板

尽量按这个结构回复：

- 已执行知乎评论抓取：`关键词=<关键词>`
- 飞书多维表格：`<feishu_bitable.url>`
- 简版图片：`<简版图片 drive_url 或 已直接发送>`
- 详细版图片：`<详细版图片 drive_url 或 已直接发送>`
- PDF：`<PDF drive_url>`
- 命中资源：`<resource_count>`
- 导出评论：`<exported_comment_count>`
- 用户画像：`<一句话总画像>`
- 4 类讨论者分布：`<4类名称/占比或高低顺序>`
- 最关注的问题：`<2-4个问题>`
- 发声目的：`<2-4个目的>`
- 高压问题标题：`<1-3个标题>`
- 本地结果：`已在画像分析后自动清理`

如果脚本返回里 `local_output.kept=true`，再补一句本地文件已保留。
如果脚本返回里没有 `feishu_bitable.url`，再退回只报真实错误，不要主推本地路径。

如果脚本输出里有 `failed_resource_count > 0`，再补一句：

- 有 `<failed_resource_count>` 个资源抓取失败，完整细节在日志文件里。

## 失败回复模板

如果脚本返回 `ok=false`，直接转述真实阻塞，例如：

- Chrome 里还没有知乎登录态
- macOS Keychain 没有在超时时间内返回 Chrome Safe Storage
- 指定的 storage-state 文件不存在

然后只给最小动作，不要扩展成长篇方案。
