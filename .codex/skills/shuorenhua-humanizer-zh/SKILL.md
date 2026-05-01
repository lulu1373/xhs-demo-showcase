---
name: shuorenhua-humanizer-zh
description: 组合 `shuorenhua` 与 `humanizer-zh` 的中文写作润色 skill，适用于“去 AI 味”“说人话”“自然一点”“中文润色”“措辞优化”“词语搭配清洗”“先标问题再改写”这类任务。先用中文语域、场景、误杀保护和 Tier/档位控制改写边界，再用结构化 AI 写作模式清单补扫内容、句法、风格、交流痕迹与填充词问题；对重叠问题只改一次，不双重重写。
metadata:
  short-description: Merge of shuorenhua + humanizer-zh for Chinese writing cleanup
---

# Shuorenhua + Humanizer-ZH

把 `shuorenhua` 的中文语域控制、误杀保护、分场景改写，与 `humanizer-zh` 的结构化 AI 痕迹清单合并成一个入口 skill。

这个 skill 的目标不是把文本统一改成某一种口气，而是：

- 先保事实、术语、责任主体和场景语域
- 再清理模板感、表演感、翻译腔、宣传腔和 AI 常见结构
- 对两套规则的重叠问题只诊断一次、只改写一次
- 不为了“更像人”而改得更假

## When to use

在下面这些需求里使用：

- 用户明确说“去 AI 味”“说人话”“自然一点”“别像模板”“别太像 ChatGPT”
- 用户要中文润色、措辞优化、局部搭配清洗、改成人写的感觉
- 用户要先做问题标注，再决定要不要改写
- 文本是中文为主，可能混有英文短语或技术术语

在下面这些需求里不要硬套：

- 用户要逐字翻译、保留原文风格、模仿特定品牌 voice 或官方模板
- 文本主要是代码、日志、命令、配置、接口名、报错
- 用户要的是事实核验，不是风格改写

## Core merge rule

这两个上游 skill 都会命中一部分相同病灶。合并后按下面的去重规则执行：

1. 先用 `shuorenhua` 判场景、禁改区、Tier 和改写档位
2. 再用 `humanizer-zh` 扫描显式模式族
3. 如果两边命中的是同一问题家族，只保留一个诊断标签和一次改写动作
4. 优先级：
   - 中文语域、误杀边界、场景保守度，优先听 `shuorenhua`
   - 明确的结构病灶、格式病灶、填充词病灶，优先听 `humanizer-zh`
   - 两边都能解释时，选更具体的那个标签
5. 不允许“为了去味”重复改写同一句两次，避免把原意洗掉

重叠映射先看 [Overlap Map](./references/overlap-map.md)。

## Execution order

按固定顺序执行，不要跳步：

1. 判任务模式：`rewrite` 或 `annotation mode`
2. 判主场景：`chat / status / docs / public-writing`
3. 划禁改区：术语、系统主语、引用原文、命令、字段名、日志、报错先保护
4. 判 Tier 和改写档位：`minimal / standard / aggressive`
5. 跑重叠去重：先对照 [Overlap Map](./references/overlap-map.md)
6. 补扫 `humanizer-zh` 的结构化模式清单
7. 只对剩余问题做一次改写
8. 先做保真回读，再按需做残留味回读
9. 输出单一推荐版本；只有用户明确要求“先标问题”时才切到 `annotation mode`

## Rewrite contract

默认输出一个推荐版本，不默认输出多版本比稿。

### Annotation mode

只有在用户明确要求下面这类事情时才启用：

- `先别改，先标问题`
- `这段哪里像 AI`
- `只做诊断 / 审稿 / 标注`
- `先告诉我该不该改`

`annotation mode` 默认只输出最重要的 1-5 个问题点。每个问题点固定包含：

- `问题族`
- `触发点`
- `建议动作`
- `是否建议改写`

## Reference loading order

这个 skill 采用“入口统一，内容分层”的结构。默认按下面顺序加载：

1. 本文件：做任务路由、场景判断、重叠去重
2. [upstream-shuorenhua.md](./references/upstream-shuorenhua.md)：作为中文场景、Tier、保护边界的主规则
3. [upstream-humanizer-zh.md](./references/upstream-humanizer-zh.md)：作为 AI 痕迹模式词典与评分规则的补充清单
4. `shuorenhua` 参考材料：按需再读具体文件

按需加载建议：

- 想看中文语域保护、Tier、场景禁改：先读 [upstream-shuorenhua.md](./references/upstream-shuorenhua.md)
- 想看 24 类 AI 写作模式、快速检查清单和评分：读 [upstream-humanizer-zh.md](./references/upstream-humanizer-zh.md)
- 想看高频中文短语：读 [phrases-zh.md](./references/phrases-zh.md)
- 想看英文短语：读 [phrases-en.md](./references/phrases-en.md)
- 想看结构问题：读 [structures.md](./references/structures.md)
- 想看误杀保护：读 [protected-spans.md](./references/protected-spans.md)
- 想看正向风格目标：读 [positive-style.md](./references/positive-style.md)
- 想看边界与例子：读 [boundary-cases.md](./references/boundary-cases.md) 和 [examples.md](./references/examples.md)
- 想看真实样本和评测：读 [real-samples.md](./references/real-samples.md) 与各 `results-*.md`

## Merge policy

- 不删信息，不做摘要式压缩
- 两份上游 `SKILL.md` 全文都保留在 `references/upstream-shuorenhua.md` 和 `references/upstream-humanizer-zh.md`
- 只在“同一病灶被两套规则重复命中”时去重
- 如果上游规则发生冲突，优先保留更保守、更不容易误伤事实的写法
- 如果用户要的是“更自然”，优先保持可直接发；如果用户要的是“更像真人”，可以适度保留观点、节奏变化和局部不完美，但不能虚构事实

## Source attribution

This skill merges and adapts content from these upstream MIT-licensed skills:

- `MrGeDiao/shuorenhua`: https://github.com/MrGeDiao/shuorenhua
- `op7418/Humanizer-zh`: https://github.com/op7418/Humanizer-zh
