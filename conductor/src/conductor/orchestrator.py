"""Orchestrator: Dev scenario Phase 0-4 flow.

Implements the core orchestration pipeline:
  Phase 0: TRIAGE  — classify task complexity (TRIVIAL/SMALL/COMPLEX)
  Phase 2: PLANNING — spawn 2 planning actors (Jobs + Torvalds), merge plan
  Phase 3: EXECUTION — spawn coding actors per plan steps
  Phase 4: QUALITY GATE — review (Martin) + testing (Beck) in parallel

Phase 1 (DISCUSSION) and Phase 5 (ACCEPTANCE) are deferred for MVP.
Iteration loop: fail → rework → re-check, up to 3 times.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Callable

from .actor import (
    TRIAGE_SCHEMA,
    spawn_actor,
    spawn_actors_parallel,
)
from .persona import (
    BECK,
    JOBS,
    MARTIN,
    TORVALDS,
    Persona,
    Specialty,
    get_persona,
)
from .state import (
    ActorStatus,
    ExecutionPlan,
    Phase,
    PlanStep,
    TaskComplexity,
    TaskState,
)
from .tmux_manager import TmuxManager


# Type for the log callback
LogFn = Callable[[str], None]


def _default_log(msg: str) -> None:
    print(msg)


class Orchestrator:
    """Dev scenario orchestrator.

    Manages the full lifecycle of a development task:
    TRIAGE → PLANNING → EXECUTION → QUALITY_GATE
    """

    def __init__(
        self,
        task_description: str,
        project_dir: str | Path,
        personas_dir: str | Path,
        tmux: TmuxManager | None = None,
        log: LogFn = _default_log,
        max_iterations: int = 3,
        actor_timeout: float = 300,
    ):
        self.project_dir = Path(project_dir)
        self.personas_dir = Path(personas_dir)
        self.tmux = tmux
        self.log = log
        self.actor_timeout = actor_timeout

        self.state = TaskState(
            task_id="task-1",
            title=task_description[:80],
            description=task_description,
            max_iterations=max_iterations,
        )

    # ── Public API ─────────────────────────────────────────────────

    async def run(self) -> TaskState:
        """Execute the full orchestration pipeline.

        Returns the final TaskState.
        """
        self.log("🎼 Conductor 编排引擎启动")
        self.log(f"📋 任务: {self.state.description[:100]}...")

        try:
            # Phase 0: Triage
            await self._phase_triage()

            if self.state.complexity == TaskComplexity.TRIVIAL:
                # TRIVIAL: skip planning, create 1 coding actor, then done
                await self._phase_execution_trivial()
            else:
                # SMALL/COMPLEX: full pipeline
                await self._phase_planning()
                await self._phase_execution()

            self.state.set_phase(Phase.DONE)
            self.log("✅ 任务完成!")

        except Exception as e:
            self.state.set_phase(Phase.FAILED)
            self.log(f"❌ 任务失败: {e}")
            raise

        return self.state

    # ── Phase 0: TRIAGE ────────────────────────────────────────────

    async def _phase_triage(self) -> None:
        """Classify task complexity."""
        self.state.set_phase(Phase.TRIAGE)
        self.log("\n━━━ Phase 0: TRIAGE（分诊）━━━")

        # Use a lightweight actor for triage
        task_context = {
            "task_id": self.state.task_id,
            "task_description": self.state.description,
        }

        if self.tmux:
            self.tmux.assign_actor("triage", "Conductor", "triage")

        actor, result = await spawn_actor(
            persona=TORVALDS,
            specialty="planning",
            task_context={
                **task_context,
                "task_description": (
                    f"分析以下任务的复杂度，判断是 TRIVIAL、SMALL 还是 COMPLEX：\n\n"
                    f"{self.state.description}\n\n"
                    f"判断标准：\n"
                    f"- TRIVIAL: 单文件/单函数修改，一步完成\n"
                    f"- SMALL: 目标清晰，不需要讨论方向\n"
                    f"- COMPLEX: 模糊需求/架构决策/多视角碰撞\n"
                ),
            },
            personas_dir=self.personas_dir,
            cwd=self.project_dir,
            timeout=60,
        )

        if self.tmux:
            self.tmux.release_pane("triage")

        # Parse triage result
        if result and "complexity" in result:
            complexity_str = result["complexity"].upper()
            try:
                self.state.complexity = TaskComplexity(complexity_str)
            except ValueError:
                self.state.complexity = TaskComplexity.SMALL
        else:
            # Default to SMALL if triage fails
            self.state.complexity = TaskComplexity.SMALL

        self.log(f"📊 判断结果: {self.state.complexity.value}")
        if result and "reasoning" in result:
            self.log(f"💡 理由: {result['reasoning']}")
        self.state.add_memory(f"Triage: {self.state.complexity.value}")

    # ── Phase 2: PLANNING ──────────────────────────────────────────

    async def _phase_planning(self) -> None:
        """Spawn 2 planning actors (Jobs + Torvalds), merge plans."""
        self.state.set_phase(Phase.PLANNING)
        self.log("\n━━━ Phase 2: PLANNING（规划）━━━")
        self.log("🧠 创建 2 个 Planning Actor: Jobs（产品视角） + Torvalds（技术视角）")

        task_context = {
            "task_id": self.state.task_id,
            "task_description": self.state.description,
        }

        # Spawn Jobs and Torvalds for planning in parallel
        configs = [
            {
                "persona": JOBS,
                "specialty": "planning",
                "task_context": {
                    **task_context,
                    "task_description": (
                        f"从产品和用户体验的角度，分析以下任务并制定执行计划：\n\n"
                        f"{self.state.description}\n\n"
                        f"重点关注：用户价值、体验标准、验收标准"
                    ),
                },
            },
            {
                "persona": TORVALDS,
                "specialty": "planning",
                "task_context": {
                    **task_context,
                    "task_description": (
                        f"从架构和实现的角度，分析以下任务并制定执行计划：\n\n"
                        f"{self.state.description}\n\n"
                        f"重点关注：技术方案、代码结构、依赖关系、可并行步骤"
                    ),
                },
            },
        ]

        # Assign tmux panes
        if self.tmux:
            self.tmux.assign_actor("planning-jobs", "Jobs", "planning")
            self.tmux.assign_actor("planning-torvalds", "Torvalds", "planning")

        results = await spawn_actors_parallel(
            configs,
            personas_dir=self.personas_dir,
            cwd=self.project_dir,
            timeout=self.actor_timeout,
        )

        # Release tmux panes
        if self.tmux:
            self.tmux.update_pane_status("planning-jobs", "done", "Jobs ✅")
            self.tmux.update_pane_status("planning-torvalds", "done", "Torvalds ✅")

        # Merge plans — Torvalds as Lead (technical projects)
        jobs_plan = results[0][1] if results[0][1] else {}
        torvalds_plan = results[1][1] if results[1][1] else {}

        self.log("📝 Jobs 的计划:")
        if jobs_plan:
            self.log(f"   分析: {jobs_plan.get('task_analysis', 'N/A')[:100]}")
            self.log(f"   步骤数: {len(jobs_plan.get('steps', []))}")

        self.log("📝 Torvalds 的计划:")
        if torvalds_plan:
            self.log(f"   分析: {torvalds_plan.get('task_analysis', 'N/A')[:100]}")
            self.log(f"   步骤数: {len(torvalds_plan.get('steps', []))}")

        # Use Torvalds' plan as the primary (technical lead)
        # Fall back to Jobs' plan if Torvalds' is empty
        primary = torvalds_plan if torvalds_plan.get("steps") else jobs_plan

        if not primary or not primary.get("steps"):
            self.log("⚠️ 两个 Planning Actor 都没产出有效计划，使用默认单步计划")
            primary = {
                "task_analysis": self.state.description,
                "steps": [
                    {
                        "step_id": 1,
                        "description": self.state.description,
                        "persona_id": "torvalds",
                        "specialty": "coding",
                        "can_parallel": False,
                        "depends_on": [],
                        "success_criteria": "Task completed successfully",
                    }
                ],
                "risks": [],
            }

        self.state.plan = ExecutionPlan.from_dict(primary)
        self.state.add_memory(
            f"Plan confirmed: {len(self.state.plan.steps)} steps"
        )
        self.log(f"\n✅ 计划确认: {len(self.state.plan.steps)} 个步骤")
        for step in self.state.plan.steps:
            parallel_mark = " ⚡" if step.can_parallel else ""
            self.log(f"   [{step.step_id}] {step.description[:60]} → {step.persona_id}/{step.specialty}{parallel_mark}")

        # Release tmux panes
        if self.tmux:
            self.tmux.release_pane("planning-jobs")
            self.tmux.release_pane("planning-torvalds")

    # ── Phase 3: EXECUTION ─────────────────────────────────────────

    async def _phase_execution(self) -> None:
        """Execute plan steps, triggering quality gate after each."""
        self.state.set_phase(Phase.EXECUTION)
        self.log("\n━━━ Phase 3: EXECUTION（执行）━━━")

        if not self.state.plan:
            raise RuntimeError("No plan to execute")

        while True:
            next_steps = self.state.plan.get_next_steps()
            if not next_steps:
                # Check if all done or some failed
                pending = [s for s in self.state.plan.steps if s.status == "pending"]
                if pending:
                    self.log(f"⚠️ {len(pending)} 个步骤被阻塞，无法继续")
                break

            # Execute next batch (parallel if possible)
            if len(next_steps) > 1 and all(s.can_parallel for s in next_steps):
                await self._execute_steps_parallel(next_steps)
            else:
                for step in next_steps:
                    await self._execute_step(step)

    async def _execute_step(self, step: PlanStep) -> None:
        """Execute a single plan step with quality gate."""
        step.status = "in_progress"
        persona = get_persona(step.persona_id)

        self.log(f"\n🔨 执行步骤 [{step.step_id}]: {step.description[:60]}")
        self.log(f"   执行者: {persona.name} ({step.specialty})")

        instance_id = f"coding-{step.persona_id}-s{step.step_id}"
        if self.tmux:
            self.tmux.assign_actor(instance_id, persona.name, step.specialty)

        task_context = {
            "task_id": self.state.task_id,
            "task_description": self.state.description,
            "assigned_step": f"步骤 {step.step_id}: {step.description}\n验收标准: {step.success_criteria}",
            "worktree_path": str(self.project_dir),
        }

        actor, result = await spawn_actor(
            persona=persona,
            specialty=step.specialty,
            task_context=task_context,
            personas_dir=self.personas_dir,
            cwd=self.project_dir,
            timeout=self.actor_timeout,
        )

        if self.tmux:
            status = "done" if actor.status == ActorStatus.DONE else "failed"
            self.tmux.update_pane_status(instance_id, status, f"{persona.name} {status}")

        if actor.status == ActorStatus.DONE:
            self.log(f"   ✅ 步骤 [{step.step_id}] 完成")
            if result:
                self.log(f"   📄 {result.get('summary', 'No summary')[:80]}")

            # Quality Gate for coding steps
            if step.specialty == "coding":
                passed = await self._phase_quality_gate(step, result)
                if passed:
                    step.status = "done"
                else:
                    step.status = "failed"
                    self.log(f"   ❌ 步骤 [{step.step_id}] 未通过质量门")
            else:
                step.status = "done"
        else:
            step.status = "failed"
            self.log(f"   ❌ 步骤 [{step.step_id}] 执行失败")

        if self.tmux:
            self.tmux.release_pane(instance_id)

    async def _execute_steps_parallel(self, steps: list[PlanStep]) -> None:
        """Execute multiple steps in parallel."""
        self.log(f"\n⚡ 并行执行 {len(steps)} 个步骤")
        tasks = [self._execute_step(step) for step in steps]
        await asyncio.gather(*tasks)

    async def _phase_execution_trivial(self) -> None:
        """Handle TRIVIAL tasks: single coding actor, no planning."""
        self.state.set_phase(Phase.EXECUTION)
        self.log("\n━━━ TRIVIAL: 直接执行 ━━━")

        instance_id = "coding-torvalds-trivial"
        if self.tmux:
            self.tmux.assign_actor(instance_id, "Torvalds", "coding")

        task_context = {
            "task_id": self.state.task_id,
            "task_description": self.state.description,
            "assigned_step": self.state.description,
            "worktree_path": str(self.project_dir),
        }

        actor, result = await spawn_actor(
            persona=TORVALDS,
            specialty="coding",
            task_context=task_context,
            personas_dir=self.personas_dir,
            cwd=self.project_dir,
            timeout=self.actor_timeout,
        )

        if self.tmux:
            status = "done" if actor.status == ActorStatus.DONE else "failed"
            self.tmux.update_pane_status(instance_id, status, f"Torvalds {status}")
            self.tmux.release_pane(instance_id)

        if actor.status == ActorStatus.DONE:
            self.log("✅ 执行完成")
            if result:
                self.log(f"📄 {result.get('summary', 'No summary')[:100]}")
        else:
            raise RuntimeError("TRIVIAL task execution failed")

    # ── Phase 4: QUALITY GATE ──────────────────────────────────────

    async def _phase_quality_gate(
        self,
        step: PlanStep,
        coding_result: dict[str, Any] | None,
    ) -> bool:
        """Run review + testing in parallel.

        Returns True if both pass, False otherwise.
        Retries up to max_iterations times.
        """
        self.state.set_phase(Phase.QUALITY_GATE)
        self.log(f"\n━━━ Phase 4: QUALITY GATE（步骤 {step.step_id}）━━━")

        for iteration in range(self.state.max_iterations):
            if iteration > 0:
                self.log(f"\n🔄 第 {iteration + 1} 次迭代")
                self.state.iterations += 1

            review_context = (
                f"审查步骤 {step.step_id} 的代码变更：{step.description}\n\n"
                f"变更摘要：{json.dumps(coding_result, ensure_ascii=False, indent=2) if coding_result else 'N/A'}"
            )

            configs = [
                {
                    "persona": MARTIN,
                    "specialty": "review",
                    "task_context": {
                        "task_id": self.state.task_id,
                        "task_description": self.state.description,
                        "review_target": review_context,
                    },
                },
                {
                    "persona": BECK,
                    "specialty": "testing",
                    "task_context": {
                        "task_id": self.state.task_id,
                        "task_description": self.state.description,
                        "review_target": (
                            f"测试步骤 {step.step_id} 的代码变更：{step.description}\n\n"
                            f"重点测试：核心逻辑 + 边界条件"
                        ),
                    },
                },
            ]

            # Assign tmux panes
            review_id = f"review-martin-s{step.step_id}-i{iteration}"
            testing_id = f"testing-beck-s{step.step_id}-i{iteration}"
            if self.tmux:
                self.tmux.assign_actor(review_id, "Martin", "review")
                self.tmux.assign_actor(testing_id, "Beck", "testing")

            self.log("👁 Martin(review) + 🧪 Beck(testing) 并行审查中...")

            results = await spawn_actors_parallel(
                configs,
                personas_dir=self.personas_dir,
                cwd=self.project_dir,
                timeout=self.actor_timeout,
            )

            # Parse results
            review_result = results[0][1] if results[0][1] else {}
            testing_result = results[1][1] if results[1][1] else {}

            review_pass = review_result.get("verdict") == "pass"
            review_score = review_result.get("score", 0)
            testing_pass = testing_result.get("verdict") == "pass"

            # Update tmux
            if self.tmux:
                self.tmux.update_pane_status(
                    review_id, "done" if review_pass else "failed",
                    f"Martin {'✅' if review_pass else '❌'} ({review_score}/10)"
                )
                self.tmux.update_pane_status(
                    testing_id, "done" if testing_pass else "failed",
                    f"Beck {'✅' if testing_pass else '❌'}"
                )
                self.tmux.release_pane(review_id)
                self.tmux.release_pane(testing_id)

            self.log(f"   👁 Review: {'PASS' if review_pass else 'FAIL'} (评分: {review_score}/10)")
            self.log(f"   🧪 Testing: {'PASS' if testing_pass else 'FAIL'}")
            if review_result.get("summary"):
                self.log(f"   📝 Review 摘要: {review_result['summary'][:80]}")
            if testing_result.get("summary"):
                self.log(f"   📝 Testing 摘要: {testing_result['summary'][:80]}")

            if review_pass and testing_pass:
                self.log("   ✅ Quality Gate 通过!")
                self.state.add_memory(
                    f"Step {step.step_id} QG passed (review={review_score}/10)"
                )
                return True

            self.log("   ⚠️ Quality Gate 未通过，需要修改")
            self.state.add_memory(
                f"Step {step.step_id} QG failed iteration {iteration + 1}"
            )

            # If not the last iteration, we'd rework here
            # For MVP, just log the failure and continue to next iteration
            if iteration < self.state.max_iterations - 1:
                self.log("   🔧 触发修改...")
                # In a full implementation, we'd spawn a coding actor
                # to fix the issues and then re-run quality gate

        self.log(f"   ❌ 超过最大迭代次数 ({self.state.max_iterations})，Quality Gate 失败")
        return False
