# Phase 4: QUALITY GATE（质量门禁）

## 目的
通过 review + testing 并行验证代码质量，确保产出达标。

## 执行步骤

### Step 1: Spawn Review + Testing Agents

**标准配置**（并行 spawn）：
- `martin-reviewer` — Clean Code 视角的代码审查
- `beck-tester` — TDD 视角的测试验证

**大型变更或架构变更时追加**：
- `torvalds-reviewer` — 架构/性能视角的代码审查

**涉及 UI 变更时追加**：
- `rams-reviewer` — 设计十诫视角的审查

### Step 2: 传递审查上下文

**传给 reviewer 的 prompt 模板**：
```
请审查以下代码变更：

## 任务背景
[总体任务描述]

## 本次变更
步骤：[步骤名]
变更描述：[coding agent 的报告]
变更文件：[文件列表]

## 执行计划（参考）
[ExecutionPlan 摘要]

## 审查要求
- 按你的审查维度逐项打分（10分制）
- ≥9 分 PASS，<9 分 FAIL
- FAIL 必须给出具体问题和修改方向
```

**传给 tester 的 prompt 模板**：
```
请测试以下代码变更：

## 任务背景
[总体任务描述]

## 本次变更
步骤：[步骤名]
变更描述：[coding agent 的报告]
变更文件：[文件列表]

## 测试要求
- 覆盖核心逻辑的正常路径
- 覆盖边界条件（空值、极值、异常输入）
- 覆盖异常路径（错误处理）
- 运行现有测试确保无回归
- 产出测试报告（PASS/FAIL + 测试用例清单）
```

### Step 3: 收集结果并判断

| 场景 | 行动 |
|------|------|
| 全部 PASS（review ≥9/10 + test PASS） | → 继续 Plan 下一步（回到 Phase 3），或所有步骤完成 → Phase 5 |
| Review FAIL | → 将 review 报告转给 coding agent，要求修改 |
| Test FAIL | → 将 test 报告（含 bug 列表）转给 coding agent，要求修复 |
| 同一步骤 fail ≥3 次 | → spawn discussion agents 讨论方案调整（升级为重新讨论方案） |
| 讨论调整后仍 fail | → 标记 BLOCKED，通知用户 |

### Step 4: 修改后重新审查

如果 coding agent 修改了代码：
1. 重新 spawn reviewer + tester（新实例，传入修改后的上下文）
2. 重复 Step 3 的判断流程
3. 跟踪迭代次数

## 迭代追踪

```
Quality Gate 迭代记录：
- Step X, Attempt 1: Review FAIL (7/10) — 命名不清晰 + 函数过长
- Step X, Attempt 2: Review PASS (9/10), Test FAIL — 边界条件未处理
- Step X, Attempt 3: All PASS ✅
```

## 失败处理
- 单个 reviewer/tester 执行失败 → 重试一次
- Review 和 Test 意见冲突 → 以 Review 的架构意见优先，Test 的 bug 必须修复
- 达到迭代上限 → spawn discussion agent 重新评估方案
