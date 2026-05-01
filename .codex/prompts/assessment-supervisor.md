---
description: "启动测评工人监督员：自动生成 Gemini 提示词、执行、复检、返工。"
argument-hint: "[书名 章节 Role 批次]"
---

加载 `assessment-supervisor` skill。

如果带了参数，把参数解析为：

- 书名标识
- 章节号
- Role
- 批次范围或返工范围

默认第一版只接 Gemini CLI。MiniMax 没有本机执行入口时，只生成 MiniMax 提示词，不声称已自动执行。

执行顺序：

1. 确认对应章节目录存在。
2. 如果是检查任务，运行：
   `python3 /Users/lulu/AIWork/scripts/assessment_supervisor.py check ...`
3. 如果是 Gemini 执行任务，运行：
   `python3 /Users/lulu/AIWork/scripts/assessment_supervisor.py run ...`
4. Role 5 写作或返工才加 `--allow-edits`。
5. 读取 `supervisor-runs/` 下的 `local-check.md`。
6. 通过则说明下一步；失败则给出返工提示词。
