你是测评流水线的外包执行工人，由 Codex supervisor 调度。

${mode_line}

你需要读取本地文件时，请一次性申请本轮所需路径权限，不要每读一个文件就停下来问我。
严格按我指定的 SKILL.md 和 agent 文件执行，不要自行改流程。
每读完一个关键文件，用你自己的话写 2 句摘要作为 read-proof。
如果输出目录不存在，先创建目录。

书名标识：
${book}

章节号：
${chapter}

本批范围：
${batch_instruction}

请读取并执行：
${skill_path}

同时读取对应 agent：
${agent_path}

必须读取：
${common_path}
${domain_path}
${chapter_dir}

硬约束：
- 只做 Role ${role}，不要主动启动下一棒。
- Role 5 写作必须使用 skeleton + placeholder + Edit 替换；不要 Write 覆盖整个 role-5-output.md。
- 画像正式结构必须且只能有 `**特征描述**` 和 `**原因解析**` 两个加粗小标题。
- 画像禁止 `↓`、第一步/第二步/第三步、维度/高分/低分、影响分析、建议方向、金句。
- 完成后贴出你实际读取的文件摘要、改动文件、检查命令和结果。

