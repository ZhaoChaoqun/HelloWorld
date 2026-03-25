"""State management for Conductor orchestration.

Manages task state, actor instances, and execution plans.
State is kept in-memory with JSON serialization for persistence.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskComplexity(str, Enum):
    TRIVIAL = "TRIVIAL"
    SMALL = "SMALL"
    COMPLEX = "COMPLEX"


class Phase(str, Enum):
    TRIAGE = "TRIAGE"
    DISCUSSION = "DISCUSSION"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    QUALITY_GATE = "QUALITY_GATE"
    ACCEPTANCE = "ACCEPTANCE"
    DONE = "DONE"
    FAILED = "FAILED"


class ActorStatus(str, Enum):
    WORKING = "working"
    DONE = "done"
    FAILED = "failed"


@dataclass
class PlanStep:
    """A single step in the execution plan."""

    step_id: int
    description: str
    persona_id: str
    specialty: str
    can_parallel: bool = False
    depends_on: list[int] = field(default_factory=list)
    success_criteria: str = ""
    status: str = "pending"  # pending | in_progress | done | failed

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "persona_id": self.persona_id,
            "specialty": self.specialty,
            "can_parallel": self.can_parallel,
            "depends_on": self.depends_on,
            "success_criteria": self.success_criteria,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(**data)


@dataclass
class ExecutionPlan:
    """The execution plan produced by planning actors."""

    task_analysis: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_analysis": self.task_analysis,
            "steps": [s.to_dict() for s in self.steps],
            "risks": self.risks,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        return cls(
            task_analysis=data.get("task_analysis", ""),
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            risks=data.get("risks", []),
        )

    def get_next_steps(self) -> list[PlanStep]:
        """Get steps that are ready to execute (dependencies met)."""
        done_ids = {s.step_id for s in self.steps if s.status == "done"}
        return [
            s
            for s in self.steps
            if s.status == "pending"
            and all(d in done_ids for d in s.depends_on)
        ]


@dataclass
class ActorInstance:
    """A running actor instance."""

    instance_id: str
    persona_id: str
    specialty: str
    thinking_mode: str  # "divergent" | "convergent"
    task_id: str
    worktree_path: str | None = None
    session_id: str | None = None
    status: ActorStatus = ActorStatus.WORKING
    activity: str = ""
    started_at: float = field(default_factory=time.time)
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "persona_id": self.persona_id,
            "specialty": self.specialty,
            "thinking_mode": self.thinking_mode,
            "task_id": self.task_id,
            "worktree_path": self.worktree_path,
            "session_id": self.session_id,
            "status": self.status.value,
            "activity": self.activity,
            "started_at": self.started_at,
        }


@dataclass
class TaskState:
    """Complete state for a single task orchestration."""

    task_id: str
    title: str
    description: str
    current_phase: Phase = Phase.TRIAGE
    complexity: TaskComplexity | None = None
    plan: ExecutionPlan | None = None
    active_actors: dict[str, ActorInstance] = field(default_factory=dict)
    completed_actors: list[str] = field(default_factory=list)
    iterations: int = 0
    max_iterations: int = 3
    memory: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_update: float = field(default_factory=time.time)

    def add_memory(self, entry: str) -> None:
        """Add an entry to the shared memory."""
        timestamp = time.strftime("%H:%M:%S")
        self.memory.append(f"[{timestamp}] {entry}")
        self.last_update = time.time()

    def set_phase(self, phase: Phase) -> None:
        self.current_phase = phase
        self.last_update = time.time()
        self.add_memory(f"Phase → {phase.value}")

    def register_actor(self, actor: ActorInstance) -> None:
        self.active_actors[actor.instance_id] = actor
        self.last_update = time.time()

    def complete_actor(self, instance_id: str, result: dict[str, Any] | None = None) -> None:
        if instance_id in self.active_actors:
            actor = self.active_actors.pop(instance_id)
            actor.status = ActorStatus.DONE
            actor.result = result
            self.completed_actors.append(instance_id)
            self.last_update = time.time()

    def fail_actor(self, instance_id: str, reason: str = "") -> None:
        if instance_id in self.active_actors:
            actor = self.active_actors.pop(instance_id)
            actor.status = ActorStatus.FAILED
            self.last_update = time.time()
            self.add_memory(f"Actor {instance_id} failed: {reason}")

    def to_status_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "current_phase": self.current_phase.value,
            "complexity": self.complexity.value if self.complexity else None,
            "active_actors": {
                k: v.to_dict() for k, v in self.active_actors.items()
            },
            "completed_actors": self.completed_actors,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "last_update": self.last_update,
        }

    def save_status(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.to_status_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def save_plan(self, path: Path) -> None:
        if self.plan:
            path.write_text(
                json.dumps(self.plan.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def save_memory(self, path: Path) -> None:
        content = f"# Task Memory: {self.title}\n\n"
        for entry in self.memory:
            content += f"- {entry}\n"
        path.write_text(content, encoding="utf-8")
