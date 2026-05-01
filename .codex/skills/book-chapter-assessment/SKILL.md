---
name: book-chapter-assessment
description: 调用书向章节测评流程与模板来完成章节测评设计。适用于 Codex 需要基于 `/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-workflow.md` 和 `/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-template.md` 处理新章节、产出章节测评文档、梳理维度与题目、设计结果页结构，或按既有规范复核已有测评稿时。
---

# Book Chapter Assessment

用这个 skill 直接进入书向章节测评流程，不要每次重新寻找文档或重建方法。

## 固定入口

每次使用这个 skill，默认先读这两个文件：

1. 流程规范：
[`/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-workflow.md`](/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-workflow.md)

2. 填写模板：
[`/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-template.md`](/Users/lulu/AIWork/docs/assessment-patterns/book-chapter-assessment-template.md)

不要跳过顺序。
先用流程规范确定做法，再按模板组织输出。

## 默认思考方法

这个 skill 默认内置使用 [`first-principles-socratic-razor` skill](/Users/lulu/.codex/skills/first-principles-socratic-razor/SKILL.md) 的思路，不需要用户额外再写一次。

做书中测评时，把这套方法主要用在四个位置：

1. 提炼章节核心痛点时
- 用第一性原理追问：这一章真正想解决的、不可再简化的问题是什么
- 把章节中的事实、作者判断、读者情绪反应、你的推断分开

2. 确定测评主题时
- 用苏格拉底提问追问主题边界：
  - 这个主题到底在测什么
  - 证据是什么
  - 有没有把章节里的局部观点误当成整章核心
  - 如果换一个相反解释，这个主题还站得住吗

3. 比较理论框架和维度时
- 不要一上来拼盘式组合概念
- 先列出 2 到 4 个可能框架，再用奥卡姆剃刀优先选那个最少假设、最少例外、最能解释章节核心痛点的框架

4. 设计结果结构和包装时
- 先保留最简单且足够成立的结果解释，再做标题和包装
- 不要为了“好卖”而先发明包装，再倒推结果结构

## 默认分析输出

如果用户没有特别要求简化，在正式填模板前，先在内部完成这一小段分析，再进入模板输出：

```markdown
## 真正问题
[这一章真正要解决什么]

## 事实与约束
- [章节里明确写出的事实或高共鸣内容]
- [本次测评必须满足的硬约束]

## 关键假设
- [当前主题或框架依赖的关键假设]

## 候选主题或框架
1. [候选项]
2. [候选项]
3. [候选项]

## 最简单且足够的选择
[为什么最终选这个主题或框架]
```

这段分析可以不完整展示给用户，但它必须实质上指导后面的主题、维度、题目和结果页设计。

## 默认工作流

1. 先阅读流程规范，提取硬约束、固定顺序、产出物要求。
2. 再阅读模板，确认本次输出需要填哪些字段和表格。
3. 如果用户给了章节内容，先提炼：
- 章节核心痛点
- 高共鸣段落
- 建议插入二维码的位置
- 可成立的测评主题

4. 按流程推进，不要倒置顺序：
- 先定主题
- 再定理论框架
- 再定一级维度
- 再写题目
- 再设计结果结构与结果文案
- 最后再定标题、包装和二维码插入文案

5. 在“定主题”和“选框架”两个节点，默认套用第一性原理、苏格拉底提问和奥卡姆剃刀做一次收敛。

6. 输出时优先直接按模板章节填写，不要另起一套结构，除非用户明确要求。

## 处理规则

- 如果用户只给了一个章节主题而没有原文，先明确标注哪些内容来自用户信息，哪些是推断。
- 如果用户要“先出个草稿”，也仍然遵守流程顺序，只是把不确定项标成待确认。
- 如果用户直接发来一份已写好的测评稿，就按流程规范反向复核，重点检查：
  - 主题是否抓住章节核心痛点
  - 维度是否来自同一理论框架且彼此平行
  - 题目是否像正式测评题，而不是聊天或培训话术
  - 结果结构是否先于包装命名
  - 二维码插入点是否和测评主题一致
- 如果用户给出多个主题、多个理论或多个包装方向，先不要平均展开，先用奥卡姆剃刀收敛到最简、最稳、最贴章的那一个。

## 题目复核

如果任务涉及正式出题或大批量修题，调用 [`Psychologist` skill](/Users/lulu/.codex/skills/academic-psychologist/SKILL.md) 辅助检查：
- 题目是否真的在测稳定倾向
- 是否带有明显“社会正确答案感”
- 是否存在构念串维度、边界不清或用户难以识别的问题

## 默认输出方式

除非用户要求别的格式，默认输出为：

1. 先给简短结论
2. 再按模板字段完整展开
3. 对推断内容加上“待确认”标记
4. 如果缺原文，单列“需要补充的章节信息”

## 最小调用示例

用户：
`用 $book-chapter-assessment 帮我把这一章做成一个二维码测评。`

用户：
`用 $book-chapter-assessment 按模板先出这一章的测评初稿。`

用户：
`用 $book-chapter-assessment 复核这份章节测评稿，看看有没有偏离流程规范。`
