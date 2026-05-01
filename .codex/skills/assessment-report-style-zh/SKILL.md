---
name: assessment-report-style-zh
description: 蒸馏并应用 `/Users/lulu/AIWork/大佬的测评/前人测评报告` 里的中文测评报告写法。用户想写、续写、改写、统一或模仿中文测评结果页、维度反馈、类型画像、长篇解读或成长建议时使用，尤其适合亲子、原生家庭、金钱、睡眠、人格风格等测评报告。
metadata:
  short-description: Write Chinese assessment reports in the distilled local house style
---

# Assessment Report Style ZH

Use this skill to write Chinese assessment reports and result pages in the style distilled from the local source reports under `/Users/lulu/AIWork/大佬的测评/前人测评报告`.

This is not a generic copywriting skill. It is specifically for:

- result pages for assessments
- dimension-by-dimension feedback
- combination/archetype interpretations
- long-form narrative reports that connect score patterns to lived experience
- actionable growth advice that stays concrete and non-preachy

## When to use

Use this skill when the user asks to:

- write a Chinese assessment report
- imitate or continue the style of existing assessment reports
- generate dimension feedback for high / medium / low scores
- write result-page copy for a questionnaire, psychometric test, or persona assessment
- turn score rules or report tables into readable Chinese feedback
- unify multiple assessment reports into one house style

Do not use this skill for:

- scale construction or psychometric validation itself
- item writing only
- plain marketing landing-page copy
- legal, medical, or diagnostic reporting
- academic paper writing

## Required inputs

Collect or infer the following before drafting:

1. Assessment topic and target user
2. Report family
3. Score logic or result type
4. Desired output format
5. Any hard constraints on length, tone, or sections

If the user gives incomplete information, infer the smallest safe structure and leave explicit placeholders rather than inventing facts.

## Report families

Choose one primary family before writing. Use [templates.md](./references/templates.md).

### Family A: Dimension report

Use when each dimension has high / medium / low or similar level-based feedback.

Typical examples:

- parenting style
- communication dimensions
- teaching wisdom index

### Family B: Combination archetype report

Use when multiple axes combine into a type, persona, or style.

Typical examples:

- communication-mode combinations
- sleep personality combinations
- money personality types

### Family C: Long-form developmental narrative

Use when the report interprets a deeper pattern across self, relationships, and future family creation.

Typical examples:

- family-of-origin pattern reports

## Workflow

### 1. Read the local source map

Start with [source-map.md](./references/source-map.md) to see which local reports are the best exemplars for the current task.

### 2. Read the distilled style guide

Read [style-guide.md](./references/style-guide.md) before drafting. It captures the stable writing moves shared across the source reports.

### 3. Pick a template family

Read [templates.md](./references/templates.md) and choose the nearest output shape. Do not merge all templates into one bloated report.

### 4. Draft from scores, not from vibes

Each paragraph must be anchored to one of these:

- a dimension level
- a type combination
- a known pattern defined by the user
- a declared theoretical lens

Do not write free-floating “洞察” that are not anchored in the result logic.

### 5. Keep the narrative sequence stable

In most cases, move in this order:

1. Name the result clearly
2. Explain what it looks like in daily life
3. Explain the likely inner mechanism or relational logic
4. State the likely effect or risk
5. Give 1-2 concrete next steps

### 6. Validate the tone and safety boundary

Before finalizing, check the guardrails in [style-guide.md](./references/style-guide.md):

- no diagnosis
- no certainty beyond the score logic
- no blame-heavy parenting language
- no fake citations
- no empty inspiration slogans

## Writing rules

### Keep the voice warm, but bounded

The house style is emotionally intelligent, explanatory, and reader-facing, but it is not mystical and not therapeutic role-play.

Write like:

- “这可能意味着……”
- “长期如此，孩子可能会……”
- “这背后常见的原因是……”
- “可以先从一个小动作开始……”

Avoid:

- “你一定是……”
- “你的创伤就是……”
- “这证明你……”
- “只要做到这些，你就会彻底改变”

### Use layered interpretation

A strong report usually has 3 layers:

1. Surface behavior or felt pattern
2. Underlying mechanism, belief, or relational logic
3. Developmental consequence or opportunity

Do not stay only on the surface, and do not jump to deep interpretation without first grounding it in recognizable behavior.

### Advice must be small enough to do

Good suggestions in this style are:

- concrete
- low-friction
- phrased as an experiment
- limited to 1-2 moves at a time

Bad suggestions are:

- abstract
- moralizing
- overloaded with steps
- framed as a personality overhaul

### Preserve reader dignity

Even when describing low-score or risky patterns:

- name the cost honestly
- explain without humiliating
- keep the user agentic

The reader should feel seen, not sentenced.

## Output expectations

Default to clean Markdown.

When the user does not specify a structure, output:

1. Title
2. Result summary
3. Main body using the selected template family
4. Growth suggestions

Do not add process notes unless the user asks for them.

## Local references

- [style-guide.md](./references/style-guide.md): distilled house style, tone, structure, and guardrails
- [templates.md](./references/templates.md): reusable section templates by report family
- [source-map.md](./references/source-map.md): where each local source report fits and what it contributes
