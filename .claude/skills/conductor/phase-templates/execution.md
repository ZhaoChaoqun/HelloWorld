# Phase 3: EXECUTION（执行）

## 目的
按 ExecutionPlan 创建 coding agent，在 worktree 中实现代码。

## 执行步骤

### Step 1: 准备执行

根据 ExecutionPlan，确定执行顺序：
- 独立步骤 → 可并行 spawn
- 有依赖的步骤 → 按依赖顺序串行
- 选择合适的 coding agent：
  - `torvalds-coder`：通用编码，擅长架构和性能
  - `beck-coder`：TDD 驱动，擅长测试先行

### Step 2: Spawn Coding Agent

**传给 coding agent 的 prompt 模板**：
```
请实现以下步骤：

## 任务背景
[总体任务描述]

## 当前步骤
步骤 X：[步骤名]
描述：[具体做什么]

## 上下文
- 项目概况：[简述]
- 相关文件：[列出关键文件路径]
- 前置步骤产出：[描述之前步骤做了什么，如有]

## 约束条件
[来自 Planning 的约束]

## 设计方案
[来自 Design 的方案，如有]

## 验收标准
- [ ] [具体标准 1]
- [ ] [具体标准 2]

## 注意事项
- 在 worktree 中工作，不要修改主分支
- 遵循项目现有的代码风格和模式
- 完成后报告：做了什么、涉及哪些文件、关键决策
```

### Step 3: 收集结果

收到 coding agent 的报告后：
1. 确认工作是否完成
2. 记录变更的文件列表
3. 决定是否需要进入 Phase 4（Quality Gate）

### 决策规则

| 情况 | 行动 |
|------|------|
| coding 完成 | → Phase 4（Quality Gate） |
| coding 报告阻塞 | → 分析原因，调整 plan 或求助用户 |
| TRIVIAL 任务完成 | → 可选 Phase 4 或直接完成 |
| 多步并行完成 | → 所有并行步骤完成后一起进 Phase 4 |

## 并行执行规则

当多个步骤标记为 `[parallel]` 时：
1. 同时 spawn 多个 coding agent
2. 每个 agent 在独立 worktree 中工作（已由 `isolation: worktree` 保证）
3. 等待所有并行 agent 完成后，统一进入 Phase 4
4. 如果某个 agent 失败，其他已完成的 agent 结果保留

## 失败处理
- Coding agent 执行失败 → 重试一次，传入错误信息
- 连续失败 → spawn discussion agent 分析原因
- 超过 2 次重试 → 标记 BLOCKED，通知用户
