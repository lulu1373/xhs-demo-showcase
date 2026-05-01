---
name: social-user-profile-universe
description: Analyze social media comments and optional avatars into a reusable Chinese user-persona universe. Use when the user wants 用户画像分析, 评论画像, 飞书多维表画像分析, CSV/XLSX 表格画像, 小红书/知乎评论分群, 小红书家庭关系议题看板, 知乎孩子议题看板, 头像风格到自我呈现再到评论表达与议题立场的链路, V3/V3.1 画像宇宙复用, 抽样人工标注, or persona dashboards/spreadsheets from social comments.
metadata:
  short-description: Social comments + avatar user persona universe
---

# Social User Profile Universe

用这套 skill 做中文社交评论的用户画像分析，尤其是“小红书/知乎评论 + 可选头像”的跨帖子、跨议题复用型画像宇宙。

先判平台，再选输出口径：

- 小红书单帖/家庭关系议题：优先做“单帖评论者画像 + 可选头像层”，看板标题可用 `小红书家庭关系议题评论者画像看板`。
- 知乎孩子议题/跨问题池：优先做“跨问题标题的讨论者画像 + 议题触发层”，不要默认放头像视觉层。

核心链路：

```text
头像风格
  -> 自我呈现方式
  -> 评论表达风格
  -> 议题立场与互动角色
```

## When To Use

使用场景：

- 用户给出评论 CSV/XLSX，要求做用户画像、评论分群、议题立场、互动角色或画像宇宙复用。
- 用户有头像图片、头像 URL、或已经人工标注的头像类型，想把头像作为“自我呈现方式”加入画像。
- 用户要求区分小红书和知乎两批评论，避免平台错配、标题错配、头像层误用。
- 用户要求抽样人工标注、回改规则、评估撞类、升级 V2/V3/V3.1。
- 用户要求生成本地表格、可视化 dashboard、汇报长图或画像结论。

不要把头像当成固定人格诊断。头像只作为自我呈现线索，必须和评论内容、议题语境、用户聚合行为一起看。

## Inputs

优先收集或自动识别：

- 评论表：`csv/xlsx`，至少有评论文本；最好有用户 ID/昵称、帖子标题、一级/二级评论关系、点赞/时间。
- 头像资料：头像图片目录、头像 URL、或已经人工标注的头像类型。
- 分析目标：单帖画像、跨帖画像、议题比较、汇报页、人工标注样本、规则验证。
- 输出格式：默认交付 `简版图片 + 详细版图片 + PDF + 原始数据表格`；HTML/JSON 只作为内部中间产物，除非用户明确要求，不作为飞书主交付入口。

## OpenClaw / 飞书小秘书入口

同事已有数据时，可以直接发给飞书小秘书做画像分析，但必须满足：

- 数据以 `CSV/XLSX/飞书多维表格` 形式提供，或提供小秘书可访问的飞书文件/表格链接。
- 消息里写清楚平台和目标，例如：`请对这个知乎评论表做用户画像分析`、`请对这批小红书评论做家庭关系议题画像`。
- 表里至少要有评论文本；最好包含用户 ID/昵称、头像 URL、帖子标题、点赞数、评论时间、一级/二级评论关系。
- 如果飞书私有文件无法读取，先让对方改发可下载的 CSV/XLSX，或把文件放到小秘书有权限的共享文件夹。
- 如果对方发的是飞书多维表 URL，例如 `https://*.feishu.cn/base/<app_token>?table=<table_id>`，不要要求对方手动导出。先在 mini 上调用：

```bash
python3 /Users/lulu/AIWork/scripts/feishu_bitable_export.py --url "<飞书多维表链接>"
```

脚本会用小秘书的 Feishu app 凭证读取表结构和记录，导出 CSV 到 `/Users/lulu/.openclaw/workspace/output/feishu_bitable_exports/`。只有当脚本返回真实权限错误或找不到表时，才让对方调整权限/导出文件。

小秘书默认交付：

- 简版图片
- 详细版图片
- PDF
- 原始数据表格

如果是在 OpenClaw / 飞书小秘书会话里触发，最终成品必须回复到触发任务的原会话/原发送人。不要在渲染脚本里写死主账号或维护者的 `open_id` 作为默认接收人。手动补救发送时，先从 gateway 日志里的 `received message from <open_id>` 或当前会话上下文确认真实发起人，再显式传入 `--feishu-receive-id`；无法确认时只生成文件夹链接，让 OpenClaw 正常 final reply 回当前会话。

不要让同事以 HTML 作为主要查看入口；HTML/JSON 只保留为源文件或复现文件。

## Workflow

1. Inspect fields: 先读字段名、样例、缺失率，确认平台信号、用户键、评论键、标题/议题键、层级键。
2. Route platform: 小红书字段常见 `note_id/red_id/xhscdn/[捂脸R]`；知乎字段常见 `question_id/title_text/author_id/zhihu.com/zhimg.com/content_text`。
3. Normalize comments: 清洗空值、去重、保留原文；不要过度压缩评论文本。
4. Route comment-level role: 用 V3 universe 给每条评论打 `domain_code`、`branch_code`、`comment_role`、`confidence`、`evidence`。
5. Aggregate user-level persona: 按用户聚合，输出 `internal_persona_code`、`persona_display_name`、`secondary_persona`、`role_stability`、`intensity`、`sample_comments`。
6. Add optional layers: 小红书有头像标注时加头像自我呈现层；知乎跨问题池优先加 `topic_trigger_matrix`，不要把头像 URL 当成已识别头像风格。
   - 若用户选择 `正式全量头像层`，对唯一头像 URL 去重，先跑自动视觉分类，再抽样复核，并在看板注明自动分类方法和复核质量。
7. Name for reporting: 对外展示用 [persona-naming-guide.md](./references/persona-naming-guide.md) 生成“好懂的人群名”，不要直接把 `S1/S4a/D2` 或“某某派”作为看板标题。
8. Validate by sampling: 每个高频域和易撞类至少抽样复核；用复核结果回改规则，再做 second pass。
9. Output artifacts: 默认落本地 `.xlsx/csv` 原始数据表格；需要汇报时生成两层图片和 PDF：`简版图片` 用于快速看分布与结论，`详细版图片` 用于用户画像详情/头像层/代表样本，`PDF` 用于飞书直接预览。HTML/JSON 仅保留为渲染中间产物，不要把 HTML 当作主要交付链接。

## Required Reference

画像宇宙细节必须从 [profile-universe-v31.md](./references/profile-universe-v31.md) 读取，尤其是：

- D1-D4 domain and branch codebook
- S1-S8, H1-H5, M1-M4 branches
- avatar A1-A9, presentation P1-P6, expression E1-E6
- stability, intensity, collision boundaries
- platform notes for XHS and Zhihu

做头像相关分析时，再读 [avatar-codebook.md](./references/avatar-codebook.md)。

做画像命名、看板标题、汇报页人群卡片时，必须读 [persona-naming-guide.md](./references/persona-naming-guide.md)。

做交付物时，再读 [output-checklist.md](./references/output-checklist.md)。

## Platform Routing

### XHS / 小红书

识别信号：

- 字段：`note_id`、`red_id`、`nickname`、`avatar`、`sub_comment_count`、`comment_image`
- URL：`xhscdn.com`
- 文本：`[捂脸R]`、`[黄金薯R]`、`[暗中观察R]` 等小红书表情

默认看板模块：

- `4 类讨论者分布`
- `讨论者最关注的问题`
- `发声目的`
- `高频情绪词`
- `高强度触发词`
- `头像风格样本`，仅在已有人工/自动头像分类时展示

头像层分三档：

- `sample_manual`: 40-100 个头像人工样本，只能用于方法验证。
- `review_sample`: 200-500 个头像分层抽样，适合方向判断。
- `full_auto`: 全量唯一头像 URL 自动分类 + 抽样复核，适合看板趋势展示。

`full_auto` 推荐产物：

- `xhs_v31_avatar_clip_v2_full.csv`: 唯一头像级分类。
- `xhs_v31_comment_layer_avatar_clip_v2.csv`: 评论层回填头像分类。
- `xhs_v31_avatar_clip_v2_summary.json`: 全量分布、置信度、人工样本命中率。
- `xhs_v31_avatar_clip_v2_audit_contact_sheet.jpg`: 抽样核验图。

如果使用 CLIP/视觉模型自动分类，必须在结果里写：

```text
头像层使用 N 个唯一头像 URL 的自动分类，结果用于趋势参考，不作为个体人格判断。
```

### Zhihu / 知乎

识别信号：

- 字段：`question_id`、`title_text`、`resource_url`、`author_id`、`author_avatar_url`、`content_text`
- URL：`zhihu.com`、`zhimg.com`
- 结构：一个关键词下跨多个问题标题、回答或评论资源

默认看板模块：

- `4 类讨论者分布`
- `讨论者最关注的问题`
- `发声目的`
- `高频情绪词`
- `高强度触发词`
- `高压问题标题`

知乎有头像 URL 不等于头像已分类。没有视觉分类时，不展示头像分布。

#### 本项目 Zhihu 孩子议题固定跑法

当用户说“跑知乎评论用户画像”“知乎孩子议题画像”且未另给新文件时，默认使用：

- 源文件：`/Users/lulu/AIWork/output/zhihu_haizi_comments_20260424.csv`
- 中间/输出目录：`/Users/lulu/AIWork/output/zhihu_haizi_v3_route/`
- 脚本目录：`/Users/lulu/AIWork/.codex_artifacts/zhihu_v3_route/`

按顺序运行：

```bash
python3 /Users/lulu/AIWork/.codex_artifacts/zhihu_v3_route/build_zhihu_v3_second_pass.py
python3 /Users/lulu/AIWork/.codex_artifacts/zhihu_v3_route/build_zhihu_v31_user_profiles.py
python3 /Users/lulu/AIWork/.codex_artifacts/zhihu_v3_route/build_zhihu_v31_persona_dashboard.py
```

核心交付物：

- `zhihu_haizi_v3_second_pass.xlsx`: 评论层 V3 second pass 标注。
- `zhihu_haizi_v31_user_profiles.xlsx`: 用户聚合画像表。
- `zhihu_haizi_v31_user_profiles_summary.json`: 用户画像统计摘要。
- `zhihu_v31_persona_dashboard_brief.jpg/png`: 简版图片，展示样本概览、4 类分布、重点问题、发声目的和关键结论。
- `zhihu_v31_persona_dashboard_detail.jpg/png`: 详细版图片，展示详细画像报告、头像自我呈现层、代表用户/评论样本和方法边界。
- `zhihu_v31_persona_dashboard.pdf`: PDF 版，用于飞书直接预览和下载。
- `zhihu_v31_persona_dashboard.html`: 渲染中间产物，默认不作为飞书主交付入口。
- `zhihu_v31_persona_dashboard_data.json`: 看板数据中间产物。

导出图片/PDF 时，用 Playwright 或 headless Chrome 打开 `zhihu_v31_persona_dashboard.html`。图片必须裁掉底部空白：若使用固定窗口截图，截图后按最后一行有效内容裁剪；优先同时产出 PDF，避免飞书把 HTML 当源码预览。导出后必须检查：

- HTML 标题包含 `知乎孩子议题评论者画像看板`。
- HTML 不包含 `小红书家庭关系议题评论者画像看板`。
- 展示画像为 `心理创伤识别型讨论者`、`情绪立场共鸣型讨论者`、`现实边界规训型讨论者`、`方法结构求解型讨论者`。
- 飞书主交付链接必须是简版图片、详细版图片、PDF、原始数据表格；HTML 链接只能作为源文件/备查。
- 长图底部不能出现大面积空白；若有空白，必须重新裁剪后再上传。
- 若未完成视觉分类，只能说明 `知乎本版未并入头像视觉层`，不要展示头像风格分布。

## Classification Rules

- 先判主功能，再判关键词。评论是在解释心理机制、结构条件、操作路径，还是只做轻互动。
- 长评论默认不要进 D4；只有主功能是附和、元评论、纠错、玩笑时才进 D4。
- D3 必须有明确行动路径、程序、方法、资源配置或处置建议。
- S6 情绪站队不是垃圾桶；能归到 S1/S2/S3/S4/S5/S7/S8/H/M 时，优先归具体分支。
- 单条评论只能代表 `L1 单条评论角色层`；用户画像必须聚合后再判断。
- 单次发声用户标注为 `单次发声`，不要写成稳定人格。
- 头像和评论冲突时，以评论证据和用户聚合为主；头像只记录“呈现方式可能不同”。

## Default Columns

评论层建议输出：

- `row_id`
- `platform`
- `platform_signal`
- `topic_title`
- `user_id`
- `comment_text`
- `comment_level`
- `domain_code`
- `branch_code`
- `comment_role`
- `expression_style`
- `confidence`
- `evidence`
- `collision_note`

用户层建议输出：

- `user_id`
- `comment_count`
- `internal_persona_code`
- `persona_display_name`
- `persona_short_name`
- `secondary_persona`
- `role_stability`
- `intensity`
- `dominant_domains`
- `avatar_type`
- `presentation_mode`
- `topic_trigger`
- `persona_summary`
- `representative_comments`
- `risk_note`

## Safety Boundaries

- 不输出“此人一定是某性别/年龄/人格”的断言。
- 性别、年龄只能作为低置信度群体倾向，不作为个体结论。
- 不做医疗、心理诊断，不贴病理标签。
- 对未成年人、家庭创伤、疾病、法律议题保持低断言和证据化表达。
- 汇报页中使用“可能呈现/更倾向/在该议题中扮演”这类措辞。
