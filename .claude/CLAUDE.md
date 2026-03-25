# Conductor 编排系统

## 使用方式

在 Claude Code 中输入 `/conductor <任务描述>` 触发 Dev 场景全流程编排。

例如：
```
/conductor 实现用户登录功能
/conductor 添加深色模式
/conductor 重构数据库访问层
```

## 编排流程概要

Conductor 会自动按以下 Phase 执行：

1. **Phase 0: TRIAGE** — 判断任务复杂度（TRIVIAL/SMALL/COMPLEX）
2. **Phase 1: DISCUSSION/DESIGN** — 多视角讨论 + 设计（仅 COMPLEX）
3. **Phase 2: PLANNING** — 产出执行计划
4. **Phase 3: EXECUTION** — 在 worktree 中编码实现
5. **Phase 4: QUALITY GATE** — 代码审查 + 测试验证
6. **Phase 5: ACCEPTANCE** — 最终产品验收

## 可用的 Agent 团队

- **Steve Jobs** (jobs-planner, jobs-reviewer) — 产品规划、用户体验验收
- **Linus Torvalds** (torvalds-planner, torvalds-coder, torvalds-reviewer) — 技术规划、编码、架构审查
- **Robert C. Martin** (martin-reviewer) — Clean Code 审查
- **Kent Beck** (beck-tester, beck-coder) — TDD 测试、编码
- **Dieter Rams** (rams-designer, rams-planner, rams-reviewer) — UI/UX 设计、设计审查

## 注意事项

- Coding agent 在 worktree 中工作，不影响主分支
- Review 和 Testing 并行执行，提高效率
- 同一步骤最多迭代 3 次，超过后停止并报告
- 每个 Phase 完成后会向用户报告进展
