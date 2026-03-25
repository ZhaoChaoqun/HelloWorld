# Phase 2: PLANNING（规划）

## 目的
产出可执行的 ExecutionPlan——步骤列表、角色分配、验收标准。

## 执行步骤

### Step 1: Spawn Planning Agents

**标准配置**（并行 spawn）：
- `jobs-planner` — 从产品/用户角度规划
- `torvalds-planner` — 从架构/技术角度规划（技术 Lead）

**涉及 UI 时追加**：
- `rams-planner` — 从设计/交互角度补充

**传给 planning agent 的 prompt 模板**：
```
请为以下任务制定执行计划：

任务：[任务描述]
[如有 Phase 1 产出]
讨论结论：[Discussion Summary]
设计方案：[Design 方案概要]
[/如有]

要求：
1. 读取项目现有代码，理解架构和约束
2. 产出步骤列表（标注可并行的步骤）
3. 每步指定执行角色（torvalds-coder / beck-coder）
4. 明确每步的验收标准
5. 识别风险和依赖
```

### Step 2: 收集并合并

1. 收集所有 planner 的产出
2. 以 **torvalds-planner 的技术方案为主干**
3. 融合 jobs-planner 的产品视角（用户故事、体验标准）
4. 融合 rams-planner 的设计视角（如有）

### Step 3: 产出 ExecutionPlan

**ExecutionPlan 格式**：
```
## ExecutionPlan

### 任务概述
[简述任务目标]

### 步骤列表

#### Step 1: [步骤名]
- 描述：[具体做什么]
- 执行者：torvalds-coder / beck-coder
- 并行标记：[独立] / [依赖 Step X]
- 交付物：[具体的文件/功能]
- 验收标准：
  - 技术标准：[...]
  - 产品标准：[...]

#### Step 2: [步骤名]
...

### 依赖关系
- Step 2 依赖 Step 1（因为...）
- Step 3 和 Step 4 可并行

### 风险清单
1. [风险描述] → [应对方案]

### 最终验收标准
- [ ] 功能标准：...
- [ ] 技术标准：...
- [ ] 用户体验标准：...
```

### Step 4: 自检

Conductor 自检 Plan 质量：
- ✅ 每个步骤是否有明确的交付物？
- ✅ 验收标准是否具体可验证（不是"正确实现"这种废话）？
- ✅ 角色分配是否合理？
- ✅ 依赖关系是否标注？
- ✅ 可并行的步骤是否标出？
- ✅ 风险是否考虑？

**不合格** → 给 planner 反馈，要求修订（最多 2 次）

## 输出

最终的 ExecutionPlan 作为 Phase 3 的输入。

## 失败处理
- Planner 产出质量不够 → 给出具体反馈重新 spawn
- 多个 planner 的方案冲突 → 以 torvalds-planner（技术 Lead）为准
- 迭代 2 次仍不合格 → 用最佳可用方案进入 Phase 3，标注风险
