# 深入理解 `--output-format` 参数

> **《Claude Code 必知必会》/ Claude Code from Zero to Hero** — 第 01 篇
>
> 这个系列面向正在学习和使用 Claude Code 的开发者。我们不翻译文档，而是用实战视角帮你真正理解每个功能的设计意图和最佳用法。

---

## 本篇概述

当你在脚本、CI/CD 或自定义 Agent 中使用 Claude Code 时，第一个要搞清楚的问题就是：**Claude 的输出长什么样？** `--output-format` 参数决定了 Claude Code 以什么格式返回结果，选错了格式，轻则解析麻烦，重则功能无法实现。

本篇将带你彻底搞懂三种输出格式的区别、适用场景，以及两个最常被问到的问题：
1. 为什么结构化数据需要 `json` + `--json-schema`，只用 `json` 不行吗？
2. 为什么自定义 Agent 编排要用 `stream-json` 而不是 `json`？

---

## 前提：`--output-format` 只在 `-p` 模式下生效

在深入之前，先明确一个前提：**`--output-format` 只在 `--print`（`-p`）模式下生效**。

`-p` 模式是 Claude Code 的"非交互模式"——你给一个 prompt，它执行完毕后输出结果然后退出，不会进入交互式对话。可以理解为 Claude Code 的"命令行工具模式"。

```bash
# 交互模式（不支持 --output-format）
claude

# -p 模式（支持 --output-format）
claude -p "解释一下这个项目的架构"
```

想象一下：交互模式就像和人面对面聊天，你不会要求对方"用 JSON 格式说话"；而 `-p` 模式是程序间的通信，你当然需要指定数据格式。

---

## 三种输出格式详解

### 1. `text`（默认） — 所见即所得

```bash
claude -p "用一句话解释什么是递归"
```

输出：

```
递归就是函数调用自身来解决问题，直到遇到一个不需要再调用自身就能解决的简单情况（基准条件）。
```

**特点**：
- 纯文本，直接输出 Claude 的回答
- 没有任何元数据（没有 session_id，没有 token 用量）
- 就像在终端里和 Claude 对话一样

**适用场景**：
- 在终端里直接看结果
- 简单的 shell 脚本，比如 `claude -p "给这段代码写个注释" | pbcopy`
- 不需要程序化处理的场景

---

### 2. `json`（一次性完整结果） — 给程序看的信封

```bash
claude -p "用一句话解释什么是递归" --output-format json
```

输出（格式化后）：

```json
{
  "type": "result",
  "subtype": "success",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "result": "递归就是函数调用自身来解决问题，直到遇到一个不需要再调用自身就能解决的简单情况（基准条件）。",
  "cost_usd": 0.003,
  "duration_ms": 1200,
  "duration_api_ms": 950,
  "is_error": false,
  "num_turns": 1,
  "usage": {
    "input_tokens": 42,
    "output_tokens": 38
  }
}
```

> 注：以上为示意，具体字段以实际运行输出为准。核心字段 `result`、`session_id`、`is_error` 在官方文档中有明确记录。

**特点**：
- 完整的 JSON 对象，包含 `result`、`session_id`、`cost_usd`、`usage` 等元数据
- **重要**：`result` 字段里的内容仍然是**自由文本**（自然语言），格式不可控
- 等 Claude 全部执行完毕后，一次性返回

**适用场景**：
- 程序化集成（解析 JSON 提取结果）
- CI/CD 流水线（获取 cost、duration 等指标）
- 需要 `session_id` 做多轮对话

```bash
# 示例：CI 中获取 session_id 用于后续对话
session_id=$(claude -p "开始代码审查" --output-format json | jq -r '.session_id')
claude -p "继续审查数据库查询部分" --resume "$session_id"
```

---

### 3. `stream-json`（实时流式） — 现场直播

```bash
claude -p "解释递归" --output-format stream-json --verbose
```

输出（每行一个 JSON 事件，即 NDJSON 格式）：

```jsonl
{"type":"system","subtype":"init","session_id":"abc-123","tools":["Read","Edit","Bash"],...}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"thinking","thinking":"用户想了解递归..."}]},...}
{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"递归是一种..."}]},...}
{"type":"result","subtype":"success","session_id":"abc-123","result":"递归是一种...","cost_usd":0.003,...}
```

**特点**：
- [NDJSON](https://github.com/ndjson/ndjson-spec) 格式：每行一个独立的 JSON 对象，实时发送
- 可以看到完整的执行过程：思考、工具调用、中间结果、最终回答
- 搭配 `--verbose` 看到详细的执行过程，搭配 `--include-partial-messages` 看到逐 token 的流式输出

**适用场景**：
- 构建自定义 UI（实时显示 Claude 的思考和操作）
- 自定义 Agent 编排（根据中间事件做实时决策）
- 实时监控和日志记录

```bash
# 示例：过滤出文本流，实时显示 Claude 的回答
claude -p "写一首诗" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages | \
  jq -rj 'select(.type == "stream_event" and .event.delta.type? == "text_delta") | .event.delta.text'
```

---

## 重点答疑（精华部分）

### 疑问一：为什么结构化数据需要 `json` + `--json-schema`，只用 `json` 不行吗？

这是最常见的误解。很多人以为 `--output-format json` 就能得到结构化的 JSON 数据。

**真相是：`--output-format json` 只是给输出套了个"信封"，`result` 里装的还是自由文本。**

来看一个对比：

#### 只用 `--output-format json`

```bash
claude -p "分析 auth.py 中的函数，返回函数名和行数" --output-format json
```

```json
{
  "type": "result",
  "subtype": "success",
  "session_id": "...",
  "result": "auth.py 中包含以下函数：\n\n1. `login()` - 第 15 行\n2. `logout()` - 第 42 行\n3. `verify_token()` - 第 68 行\n\n共 3 个函数。",
  "cost_usd": 0.004,
  "is_error": false
}
```

注意看 `result` 字段 —— 它是一段**自然语言文本**，带着 Markdown 格式。你要用程序解析出函数名和行号？那你得自己写正则表达式去提取，而且下次 Claude 可能换个表达方式，你的正则就炸了。

#### 用 `--output-format json` + `--json-schema`

```bash
claude -p "分析 auth.py 中的函数，返回函数名和行数" \
  --output-format json \
  --json-schema '{
    "type": "object",
    "properties": {
      "functions": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "name": { "type": "string" },
            "line": { "type": "integer" }
          },
          "required": ["name", "line"]
        }
      }
    },
    "required": ["functions"]
  }'
```

```json
{
  "type": "result",
  "subtype": "success",
  "session_id": "...",
  "result": "...",
  "structured_output": {
    "functions": [
      { "name": "login", "line": 15 },
      { "name": "logout", "line": 42 },
      { "name": "verify_token", "line": 68 }
    ]
  },
  "cost_usd": 0.005,
  "is_error": false
}
```

看到区别了吗？**结构化的数据出现在 `structured_output` 字段**，严格符合你定义的 JSON Schema，程序可以直接 `jq '.structured_output.functions'` 拿到干净的数据。

#### 一句话总结

| | `--output-format json` | `--output-format json` + `--json-schema` |
|---|---|---|
| **输出格式** | JSON 信封 | JSON 信封 |
| **result 字段** | 自由文本（不可控） | 自由文本（不可控） |
| **structured_output 字段** | 无 | 严格符合 Schema 的结构化数据 |
| **程序能直接用？** | 需要自己解析文本 | 直接用，类型安全 |

**类比**：`--output-format json` 就像把一封手写信装进了标准信封（有收件人、邮编等元数据），但信的内容还是自由格式的；`--json-schema` 则像是给信的内容也提供了一个标准表格——必须按格式填写，一个字段都不能少。

---

### 疑问二：为什么自定义 Agent 编排要用 `stream-json` 而不是 `json`？

这个问题的答案藏在一个关键的时序差异里。

#### `json` 模式：寄快递

```
你下单 ──────── 等待（黑箱）──────── 收到包裹
                  ↑
          这段时间你什么都不知道：
          - 发货了吗？
          - 到哪了？
          - 出问题了吗？
```

用 `json` 模式运行 Claude：

```bash
claude -p "审查代码并修复所有 bug" --output-format json
```

你会盯着终端看，什么也没有……过了 30 秒、60 秒、120 秒……突然一大坨 JSON 砸过来。这期间：
- Claude 可能在读文件 → 你不知道
- Claude 可能在执行命令 → 你不知道
- Claude 可能遇到错误在重试 → 你不知道
- Claude 可能思考了半天走了弯路 → 你不知道

#### `stream-json` 模式：实时物流追踪

```
你下单 → 已揽收 → 运输中 → 到达中转站 → 派送中 → 已签收
    ↑        ↑         ↑          ↑           ↑        ↑
  每一步都有实时更新
```

用 `stream-json` 模式运行 Claude：

```bash
claude -p "审查代码并修复所有 bug" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages
```

你会实时看到每一个事件（以下为简化示意，实际事件结构以 Claude Code 输出为准）：

```jsonl
{"type":"system","subtype":"init","session_id":"abc-123",...}
{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"让我先看看项目结构..."}]},...}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"find . -name '*.py'"}}]},...}
{"type":"assistant","message":{"content":[{"type":"tool_result","output":"./auth.py\n./main.py\n./utils.py"}]},...}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","input":{"file_path":"./auth.py"}}]},...}
{"type":"assistant","message":{"content":[{"type":"text","text":"发现 auth.py 第 42 行有一个未处理的异常..."}]},...}
{"type":"result","subtype":"success","result":"已修复 3 个 bug...","cost_usd":0.05,...}
```

#### 为什么 Agent 编排必须要实时？

构建自定义 Agent 编排系统时，你需要的不是"最终结果"，而是"过程控制"：

| 需求 | `json` 能做到吗？ | `stream-json` 能做到吗？ |
|---|---|---|
| **实时展示**：在 UI 上显示 Claude 正在做什么 | 不能，只能转圈 | 可以，逐事件更新 |
| **实时决策**：看到 Claude 要执行危险命令时拦截 | 不能，木已成舟 | 可以，拦截 tool_use 事件 |
| **超时控制**：某个步骤超时就中断 | 只能控制整体超时 | 可以精确到每个步骤 |
| **进度追踪**：知道当前执行到哪一步 | 不能 | 可以 |
| **错误恢复**：某步失败时介入处理 | 不能 | 可以 |
| **逐事件日志**：记录完整的执行轨迹 | 只有最终结果 | 完整的事件流 |
| **重试监控**：知道 API 在重试 | 不能 | 收到 `system/api_retry` 事件 |

**一句话总结**：`json` 是"给我结果就行"，`stream-json` 是"我要盯着你干活"。做 Agent 编排，你必须盯着干活。

---

## 场景速查表

| 你想做的事 | 推荐格式 | 示例 |
|---|---|---|
| 终端里快速问个问题 | `text` | `claude -p "解释一下这段代码"` |
| Shell 脚本中获取回答 | `text` | `claude -p "生成 commit message" \| pbcopy` |
| CI/CD 中获取执行指标 | `json` | `claude -p "跑测试" --output-format json \| jq '.cost_usd'` |
| 多轮对话（程序化） | `json` | 提取 `session_id`，用 `--resume` 继续 |
| 获取结构化数据 | `json` + `--json-schema` | 提取函数列表、分析报告等 |
| 构建自定义 UI | `stream-json` | 实时展示 Claude 的思考和操作 |
| 自定义 Agent 编排 | `stream-json` | 实时监控、决策、拦截 |
| 调试 Claude 的行为 | `stream-json` + `--verbose` | 看完整的推理和工具调用过程 |
| 逐 token 流式输出 | `stream-json` + `--include-partial-messages` | 打字机效果的 UI |

---

## 相关参数搭配速查

| 参数 | 搭配 | 作用 |
|---|---|---|
| `--json-schema '{...}'` | `--output-format json` | 强制输出符合 Schema 的结构化数据，结果在 `structured_output` 字段 |
| `--verbose` | `--output-format stream-json` | 显示详细的执行过程（思考、工具调用等） |
| `--include-partial-messages` | `--output-format stream-json` | 逐 token 流式输出，实现"打字机效果" |
| `--max-turns N` | `-p` | 限制 agentic 执行的轮数，防止无限循环 |
| `--max-budget-usd N` | `-p` | 限制 API 花费，超出则停止 |
| `--allowedTools "..."` | `-p` | 自动批准指定工具，无需手动确认 |

---

## 总结

三种格式的选择其实很简单：

```
你是人类在终端看？          → text
你的程序需要结果？          → json
你的程序需要结果 + 过程？   → stream-json

需要结构化数据？            → json + --json-schema
需要逐 token 流式？         → stream-json + --include-partial-messages
```

记住两个核心认知：
1. **`json` ≠ 结构化数据**。`json` 只是信封，`--json-schema` 才是内容的模具。
2. **Agent 编排 = 过程控制**。控制过程需要实时信息，所以必须用 `stream-json`。

---

## 参考资料

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-usage) — CLI 命令和参数完整参考
- [Run Claude Code Programmatically](https://code.claude.com/docs/en/headless) — 程序化使用 Claude Code 的详细指南

---

> **下一篇预告**：敬请期待《Claude Code 必知必会》第 02 篇。
>
> 如果这篇文章对你有帮助，欢迎 Star 这个仓库 :)
