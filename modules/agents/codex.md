## Codex

你运行在 Codex Harness 中。每个会话是一个 Thread（有 id 和名字，可恢复、可分叉）；子 Agent 也是 Thread。工具调用和 shell 是同一能力的两个入口，选哪个入口不重要，重要的是你决定让新 Thread 看见多少你的历史：

- 工具层：`spawn_agent` 新建子 Agent，`fork_turns` 控制它继承你多少对话历史，**默认 `all`**——默认值站在「延续」一边，探索和复核必须显式传 `"none"` 并把所需上下文写进 `message`。`send_input` / `followup_task` 复用现有 Agent；`wait_agent` 等待并收割结果。
- Shell 层：`codex exec -C <dir> "<task>"` 起干净的新 Thread，`-o <file>` 把最终回复写进文件；`codex exec resume <id|name> "<prompt>"` 延续既有 Thread 的全部历史；`codex fork` 分叉出平行现场做对照实验。
- 子 Agent 默认用 GPT-5.5 High；`reasoning_effort` 不传则继承你的档位。
