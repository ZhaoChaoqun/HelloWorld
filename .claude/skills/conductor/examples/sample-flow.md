# 示例流程：`/conductor 实现用户登录功能`

## 完整编排流程演示

### Phase 0: TRIAGE

```
Conductor 分析任务：

任务："实现用户登录功能"

判断：
- 涉及认证方案选择（JWT vs Session）→ 架构决策
- 涉及登录表单 UI → 前端设计
- 涉及多文件（API、数据库、前端、中间件）→ 多模块联动

结论：COMPLEX → 进入 Phase 1
注意：涉及 UI，Phase 1 需要先 spawn rams-designer 出设计方案
```

---

### Phase 1: DISCUSSION / DESIGN

**Step 1: Design First**

```
Conductor spawns:
  Agent(subagent_type="rams-designer", prompt="请为用户登录功能出设计方案...")

Rams 产出：
- 登录页布局（居中卡片式）
- 表单字段：邮箱 + 密码 + 记住我
- 错误状态：字段级 + 表单级
- 登录成功动画 → 跳转首页
- 色值、间距、字号规范
```

**Step 2: Multi-Perspective Discussion**

```
Conductor 并行 spawns:
  Agent(subagent_type="jobs-planner", prompt="从产品/用户体验角度分析登录功能...")
  Agent(subagent_type="torvalds-planner", prompt="从架构/技术角度分析登录功能...")

Jobs 观点：
- 登录应该尽可能快（< 2步）
- 错误提示要友好（"邮箱或密码不正确"——安全考虑）
- 需要"忘记密码"入口

Torvalds 观点：
- JWT 方案，无状态，好扩展
- bcrypt 加密存储密码
- Rate limiting 防暴力破解

Conductor 决策：
- 采用 JWT（Torvalds 建议）
- 体验按 Jobs 标准
- UI 按 Rams 设计方案
- MVP 不做"忘记密码"
```

---

### Phase 2: PLANNING

```
Conductor 并行 spawns:
  Agent(subagent_type="jobs-planner", prompt="从产品角度规划登录功能实现步骤...")
  Agent(subagent_type="torvalds-planner", prompt="从技术角度规划登录功能实现步骤...")
  Agent(subagent_type="rams-planner", prompt="从设计角度补充登录功能规划...")

Conductor 合并产出最终 ExecutionPlan：

Step 1: 用户数据模型 + 数据库 [独立]
  - 执行者：torvalds-coder

Step 2: 认证 API [依赖 Step 1]
  - 执行者：torvalds-coder

Step 3: 登录页面 UI [可与 Step 2 并行]
  - 执行者：beck-coder

Step 4: 集成联调 [依赖 Step 2, 3]
  - 执行者：torvalds-coder
```

---

### Phase 3 → 4 循环

**Step 1 执行 + 审查**：
```
Phase 3: spawn Agent(subagent_type="torvalds-coder", prompt="实现用户数据模型...")
Phase 4: spawn Agent(subagent_type="martin-reviewer") + Agent(subagent_type="beck-tester")
→ All PASS ✅
```

**Step 2 + Step 3 并行执行 + 审查**：
```
Phase 3: 并行 spawn torvalds-coder(Step 2) + beck-coder(Step 3)
Phase 4: spawn martin-reviewer + beck-tester + rams-reviewer(UI)
→ Beck-tester 发现 bug（空密码返回 500）
→ 打回 torvalds-coder 修复
→ 重新审查 → All PASS ✅
```

**Step 4 执行 + 审查**：
```
Phase 3: spawn torvalds-coder(集成联调)
Phase 4: spawn martin-reviewer + torvalds-reviewer + beck-tester
→ All PASS ✅
```

---

### Phase 5: ACCEPTANCE

```
spawn Agent(subagent_type="jobs-reviewer", prompt="验收用户登录功能...")

Jobs 验收：PASS ✅
- 登录 2 步完成
- 错误提示友好
- 视觉品质达标
- 建议：后续加"忘记密码"
```

---

### 最终报告

```
## ✅ 任务完成报告

### 任务
实现用户登录功能

### 执行摘要
- 复杂度：COMPLEX
- 阶段：Phase 0 → 1 → 2 → 3 → 4 → 5
- 迭代：2（Step 2 Quality Gate 迭代 1 次）

### 交付物
- models/user.py, api/auth.py, middleware/auth.py
- components/LoginForm.tsx
- migrations/001_create_users.py
- tests/

### 质量验证
- Review: 9/10 (martin), 9.5/10 (torvalds)
- Testing: PASS (beck, 15 cases)
- Acceptance: PASS (jobs)
```
