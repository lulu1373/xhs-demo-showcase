# Output Checklist

用于交付画像分析表格、dashboard、汇报图片和 PDF 前的检查。

## 0. Default Delivery Package

后续爬虫/画像默认只把这些作为主交付：

- `简版图片`: 快速总览，包含样本概览、4 类分布、重点问题、发声目的和关键结论。
- `详细版图片`: 详细画像报告，包含每类画像解释、代表用户/评论样本；若完成头像视觉分类，必须把头像自我呈现层并入对应画像详情。
- `PDF`: 与详细版内容一致或覆盖完整报告，用于飞书直接预览/下载。
- `原始数据表格`: 评论原始数据、评论层标注、用户聚合画像；可用 CSV/XLSX/飞书多维表格。

HTML/JSON 只作为渲染和复现用中间产物。飞书主链接不要默认给 HTML，因为飞书会按源码预览。图片必须裁掉底部空白后再上传。

## 0.1 Visual Template Contract

画像汇报图默认使用 V3.1 两层模板，不要临时换成海报、信息图或纯 Markdown 长图风格，除非用户明确要求改版。

模板结构：

- `简版图片`: V3.1 hero 标题区 + 样本统计卡 + 4 类画像卡 + 高频/高压话题条形图 + 高频情绪词 + 高强度触发词 + `第一层：汇报看板` + 核心判断。
- `详细版图片`: 同一套 V3.1 hero 和统计区 + 4 类画像卡 + 每类画像的情绪强度/高频情绪词 + `第一层：汇报看板` + `第二层：详细画像报告` + 每类用户的需求、情绪触发、表达边界、内容启发、代表评论证据；如果已做头像视觉分类，头像自我呈现层必须并入每类画像详情。
- `PDF`: 与图片使用同一份 HTML/template source 导出，保证视觉风格一致。
- `原始数据表格`: 与图片/PDF 放在同一个飞书交付文件夹。

视觉约束：

- 复用 V3/V3.1 画像宇宙风格：浅色背景、顶部大标题、统计卡、分层标签、画像卡片、条形图。
- 情绪分析是画像模板的固定模块：全局要有 `高频情绪词` 和 `高强度触发词`，详细画像里每类要有情绪强度、情绪词和触发词。
- 头像分析不能只写“已抓取 URL”状态；只要完成头像下载/分类，就必须并入详细画像，展示 A1-A9 头像类型、P1-P6 自我呈现、代表头像样本和方法边界。
- 不要把 HTML 链接作为主交付，因为飞书会按源码预览。
- 长图必须按最后有效文字/卡片内容裁剪，底部不能保留大面积空白。
- 手动补救发送时，必须回复触发任务的原会话/原发送人；不要把维护者或主账号 `open_id` 写死成默认接收人。

## 1. Spreadsheet Outputs

默认至少输出两个 sheet：

- `comment_layer`: 单条评论标注。
- `user_profiles`: 用户聚合画像。

可选 sheet：

- `codebook`: 本次使用的 domain/branch/persona 说明。
- `review_samples`: 人工复核样本。
- `collision_cases`: 撞类和低置信度样本。
- `topic_compare`: 跨标题/跨议题对比。

先做数据源核验，避免平台错配：

- 小红书信号：`note_id`、`red_id`、`nickname`、`avatar`、`xhscdn.com`、`[捂脸R]`。
- 知乎信号：`question_id`、`title_text`、`author_id`、`author_avatar_url`、`zhihu.com`、`zhimg.com`、`content_text`。
- 输出里保留 `platform` 和 `platform_signal`，必要时在看板脚注写清楚数据源。

评论层字段：

- `row_id`
- `platform`
- `topic_title`
- `user_id`
- `comment_text`
- `comment_level`
- `parent_comment_id`
- `domain_code`
- `branch_code`
- `comment_role`
- `expression_style`
- `confidence`
- `evidence`
- `collision_note`

用户层字段：

- `user_id`
- `comment_count`
- `internal_persona_code`
- `internal_persona_label`
- `persona_display_name`
- `persona_short_name`
- `secondary_persona`
- `role_stability`
- `intensity`
- `dominant_domains`
- `dominant_branches`
- `avatar_type`
- `presentation_mode`
- `persona_summary`
- `representative_comments`
- `risk_note`

## 2. Dashboard Sections

汇报型 dashboard 建议包含：

- `样本概览`: 平台、评论数、用户数、一级/二级评论比例、有效头像数。
- `N 类用户/家长分布`: 使用 `persona_display_name`，例如 `关系沟通修复型家长`，不要直接展示 `S2/S7/H3`。
- `用户最关注的问题`: 按议题词或关注问题聚合，例如 `自主成长与独立`、`沟通断裂`、`情绪管理`。
- `发声目的`: 例如 `观点表达`、`吐槽宣泄`、`方法建议`、`寻求共鸣`、`科普解读`、`经验分享`。
- `高频情绪词`: 展示中性词、正向词、负向词的数量。
- `高强度触发词`: 只放高强度样本里反复出现的情绪/冲突词。
- `画像卡片`: 每类人群的核心特征、主要关注问题、情绪正负性、情绪强度、高频词、发帖目的、典型样本标题。
- `撞类与边界`: 说明哪些类型最容易混淆，以及规则如何处理。
- `可复用性评估`: 跨帖子/跨议题稳定的类，和需要继续扩展的类。

### XHS dashboard

小红书家庭关系议题推荐标题：

- `小红书家庭关系议题评论者画像看板`

推荐 4 类展示画像：

- `轻共鸣接梗型讨论者`
- `专业真实性鉴别型讨论者`
- `自主边界守护型讨论者`
- `问题解决与成因拆解型讨论者`

推荐模块：

- `4 类讨论者分布`
- `讨论者最关注的问题`
- `发声目的`
- `高频情绪词`
- `高强度触发词`
- `头像风格样本`
- `画像卡片`

头像只有部分人工标注时，必须注明：

```text
头像层目前使用 N 条人工标注样本，不代表全量头像分布。
```

全量头像自动分类时，必须注明：

```text
头像层使用 N 个唯一头像 URL 的自动分类，其中 M 个保留人工标注；结果用于趋势参考，不作为个体人格判断。
```

全量头像层建议检查：

- `unique_avatar_urls`: 唯一头像 URL 数。
- `final_annotation_status_counts`: 自动分类与人工保留数量。
- `avatar_style_counts_unique`: 按唯一头像计数。
- `avatar_style_counts_comment_weighted`: 按评论行加权计数。
- `presentation_counts_unique`: 自我呈现方式分布。
- `confidence_counts_unique`: 模型置信度分布。
- `manual_eval_*`: 人工样本对齐命中率或复核结果。
- `audit_contact_sheet`: 抽样核验图。

本项目 `clip_v2` 小红书全量头像层产物：

- `xhs_v31_avatar_clip_v2_full.csv`
- `xhs_v31_comment_layer_avatar_clip_v2.csv`
- `xhs_v31_avatar_clip_v2_summary.json`
- `xhs_v31_avatar_clip_v2_audit_contact_sheet.jpg`

### Zhihu dashboard

知乎孩子议题推荐标题：

- `知乎孩子议题评论者画像看板`

推荐 4 类展示画像：

- `心理创伤识别型讨论者`
- `情绪立场共鸣型讨论者`
- `现实边界规训型讨论者`
- `方法结构求解型讨论者`

推荐模块：

- `4 类讨论者分布`
- `讨论者最关注的问题`
- `发声目的`
- `高频情绪词`
- `高强度触发词`
- `高压问题标题`
- `画像卡片`

知乎如果只有 `author_avatar_url`，不要写头像风格分布。只有在完成头像视觉分类后，才展示头像层。

默认交付命名建议：

- `zhihu_{topic}_v31_brief.jpg/png`: 简版图片。
- `zhihu_{topic}_v31_detail.jpg/png`: 详细版图片。
- `zhihu_{topic}_v31_report.pdf`: PDF 版。
- `zhihu_{topic}_v31_raw_comments.csv/xlsx`: 原始评论数据表。
- `zhihu_{topic}_v31_comment_layer.csv/xlsx`: 评论层标注表。
- `zhihu_{topic}_v31_user_profiles.csv/xlsx`: 用户聚合画像表。

HTML/JSON 命名可保留，但只作为内部中间产物或用户明确要求时交付。

看板标题优先使用业务语言：

- 好：`4 类家长分布`
- 好：`家长最关注的问题`
- 好：`情绪强度总览`
- 避免：`D1-D4 分布`
- 避免：`S1/S2/S3 Persona Overview`
- 避免：`反投射者占比`

## 3. Summary Language

推荐措辞：

- “在该议题中更常扮演……”
- “该账号公开呈现更接近……”
- “从评论证据看，主角色是……”
- “该类人群的主要发声功能是……”
- “这不是个体人格诊断，而是平台互动角色画像。”
- “这类家长最关注的是……”
- “这类用户的发声目的更偏向……”

避免措辞：

- “这类人就是……”
- “他们的真实性格是……”
- “头像证明……”
- “一定/必然/绝对。”
- “S4a 型用户最……”

## 4. Sampling Validation

每轮自动/半自动标注后，至少做：

- 高频类别各抽 10-20 条。
- D3/D4 各抽 20 条，重点检查是否过度分类。
- 低置信度样本集中复核。
- 撞类边界样本单独列出。
- 复核后做 `second_pass`，不要只改结论不改规则。

## 5. Reusability Assessment

结论里必须回答：

- 哪些类跨帖子稳定？
- 哪些类依赖特定平台语境？
- 哪些类容易撞类？
- 是否需要新增 domain/branch，还是调整边界规则即可？
- 单次发声用户比例是否过高，是否影响用户层画像稳定性？

## 6. File Naming

建议命名：

- `{platform}_{topic}_v31_comment_layer.csv`
- `{platform}_{topic}_v31_user_profiles.xlsx`
- `{platform}_{topic}_v31_brief.jpg`
- `{platform}_{topic}_v31_detail.jpg`
- `{platform}_{topic}_v31_report.pdf`
- `{platform}_{topic}_v31_persona_dashboard.html`，仅中间产物/源文件
- `{platform}_{topic}_v31_second_pass.xlsx`
- `{platform}_{topic}_v31_avatar_clip_v2_full.csv`
- `{platform}_{topic}_v31_avatar_clip_v2_summary.json`
- `{platform}_{topic}_v31_avatar_clip_v2_audit_contact_sheet.jpg`

本项目已使用过的命名：

- `xhs_v31_persona_dashboard.html`: 小红书家庭关系议题。
- `zhihu_v31_persona_dashboard.html`: 知乎孩子议题。
