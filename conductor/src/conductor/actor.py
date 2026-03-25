"""Actor lifecycle management with Claude Agent SDK.

Handles spawning, monitoring, and collecting results from Actor instances.
Each Actor is a Claude instance with a persona × specialty prompt.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from .persona import SPECIALTY_THINKING, Persona, Specialty
from .prompt_builder import build_actor_prompt
from .state import ActorInstance, ActorStatus


# ── Structured Output Schemas ──────────────────────────────────────────

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "complexity": {
            "type": "string",
            "enum": ["TRIVIAL", "SMALL", "COMPLEX"],
        },
        "reasoning": {"type": "string"},
        "suggested_approach": {"type": "string"},
    },
    "required": ["complexity", "reasoning"],
}

PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "task_analysis": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "integer"},
                    "description": {"type": "string"},
                    "persona_id": {"type": "string"},
                    "specialty": {"type": "string"},
                    "can_parallel": {"type": "boolean"},
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "success_criteria": {"type": "string"},
                },
                "required": ["step_id", "description", "persona_id", "specialty"],
            },
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["task_analysis", "steps"],
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 10},
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "minor", "suggestion"],
                    },
                    "description": {"type": "string"},
                    "file": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "description"],
            },
        },
    },
    "required": ["score", "verdict", "summary"],
}

TESTING_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "summary": {"type": "string"},
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "result": {"type": "string", "enum": ["pass", "fail"]},
                    "details": {"type": "string"},
                },
                "required": ["name", "result"],
            },
        },
        "bugs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string"},
                    "description": {"type": "string"},
                    "reproduction_steps": {"type": "string"},
                },
                "required": ["severity", "description"],
            },
        },
    },
    "required": ["verdict", "summary"],
}

CODING_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "files_changed": {
            "type": "array",
            "items": {"type": "string"},
        },
        "design_decisions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "edge_cases_handled": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["summary", "files_changed"],
}

# Specialty → schema mapping
SPECIALTY_SCHEMAS: dict[str, dict[str, Any]] = {
    "planning": PLANNING_SCHEMA,
    "review": REVIEW_SCHEMA,
    "testing": TESTING_SCHEMA,
    "coding": CODING_SCHEMA,
}


# ── Tool Permissions ───────────────────────────────────────────────────

SPECIALTY_TOOLS: dict[str, list[str]] = {
    "planning": ["Read", "Grep", "Glob", "Bash"],
    "discussion": ["Read", "Grep", "Glob"],
    "coding": ["Read", "Write", "Edit", "Bash", "Grep", "Glob"],
    "review": ["Read", "Grep", "Glob", "Bash"],
    "testing": ["Read", "Grep", "Glob", "Bash"],
    "design": ["Read", "Grep", "Glob"],
}


# ── Actor Spawning ─────────────────────────────────────────────────────

async def spawn_actor(
    persona: Persona,
    specialty: Specialty,
    task_context: dict[str, str],
    personas_dir: Path,
    cwd: str | Path | None = None,
    timeout: float = 300,
) -> tuple[ActorInstance, dict[str, Any] | None]:
    """Spawn an actor and wait for its result.

    Creates a Claude instance with the generated prompt, runs the query,
    and collects the structured output.

    Args:
        persona: The persona to use.
        specialty: The specialty to perform.
        task_context: Dynamic task context for prompt generation.
        personas_dir: Path to persona .md files.
        cwd: Working directory for the actor.
        timeout: Maximum seconds to wait for the actor.

    Returns:
        Tuple of (ActorInstance, structured_output or None).
    """
    instance_id = f"{specialty}-{persona.id}"
    thinking_mode = SPECIALTY_THINKING.get(specialty, "convergent")

    actor = ActorInstance(
        instance_id=instance_id,
        persona_id=persona.id,
        specialty=specialty,
        thinking_mode=thinking_mode,
        task_id=task_context.get("task_id", "unknown"),
        worktree_path=task_context.get("worktree_path"),
        activity=f"{persona.name} doing {specialty}",
    )

    # Build the system prompt
    system_prompt = build_actor_prompt(
        persona=persona,
        specialty=specialty,
        task_context=task_context,
        personas_dir=personas_dir,
    )

    # Build the task prompt (what the actor should actually do)
    task_prompt = task_context.get("task_description", "")
    if specialty == "review":
        task_prompt = task_context.get("review_target", task_prompt)
    elif specialty == "coding":
        step_desc = task_context.get("assigned_step", "")
        if step_desc:
            task_prompt = f"执行以下步骤：\n{step_desc}\n\n任务背景：\n{task_prompt}"

    # Configure Agent SDK options
    schema = SPECIALTY_SCHEMAS.get(specialty)
    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=SPECIALTY_TOOLS.get(specialty, ["Read", "Grep", "Glob"]),
        permission_mode="bypassPermissions",
        cwd=str(cwd) if cwd else None,
        max_turns=50,
    )

    if schema:
        options.output_format = {"type": "json_schema", "schema": schema}

    # Run the actor with timeout
    structured_output = None
    session_id = None

    try:
        async with asyncio.timeout(timeout):
            async for message in query(prompt=task_prompt, options=options):
                # Capture session ID from init event
                if hasattr(message, "subtype") and message.subtype == "init":
                    session_id = getattr(message, "session_id", None)
                    actor.session_id = session_id

                # Capture result
                if isinstance(message, ResultMessage):
                    if message.subtype == "success":
                        structured_output = message.structured_output
                        actor.status = ActorStatus.DONE
                    else:
                        actor.status = ActorStatus.FAILED

    except TimeoutError:
        actor.status = ActorStatus.FAILED
        actor.activity = f"Timed out after {timeout}s"
    except Exception as e:
        actor.status = ActorStatus.FAILED
        actor.activity = f"Error: {e}"

    actor.result = structured_output
    return actor, structured_output


async def spawn_actors_parallel(
    actors_config: list[dict[str, Any]],
    personas_dir: Path,
    cwd: str | Path | None = None,
    timeout: float = 300,
) -> list[tuple[ActorInstance, dict[str, Any] | None]]:
    """Spawn multiple actors in parallel and collect results.

    Args:
        actors_config: List of dicts with keys:
            - persona: Persona instance
            - specialty: Specialty string
            - task_context: Dict of context values
        personas_dir: Path to persona .md files.
        cwd: Working directory.
        timeout: Timeout per actor.

    Returns:
        List of (ActorInstance, result) tuples.
    """
    tasks = [
        spawn_actor(
            persona=cfg["persona"],
            specialty=cfg["specialty"],
            task_context=cfg["task_context"],
            personas_dir=personas_dir,
            cwd=cfg.get("cwd", cwd),
            timeout=timeout,
        )
        for cfg in actors_config
    ]
    return list(await asyncio.gather(*tasks, return_exceptions=False))
