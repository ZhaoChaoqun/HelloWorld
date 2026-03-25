"""CLAUDE.md three-section prompt generator.

Generates actor-specific system prompts by combining:
  1. Persona base (personality, thinking style)
  2. Specialty behavior (work methods, output format, constraints)
  3. Task context (dynamic: task description, paths, etc.)

Each persona × specialty combination produces a unique CLAUDE.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .persona import (
    SPECIALTY_DISPLAY,
    SPECIALTY_THINKING,
    Persona,
    Specialty,
)

# ── Specialty Behavior Templates ───────────────────────────────────────
# Each function returns (behavior_text, output_format, tool_rules) for a
# given persona × specialty combination. The behavior is personalized
# based on the persona's unique traits.

def _planning_behavior(persona: Persona) -> tuple[str, str, str]:
    """Generate planning specialty behavior, personalized per persona."""
    persona_specific = {
        "jobs": (
            "你不是技术人员，你是产品的守护者：\n"
            "- **用户视角优先**：每一步都要问「这对用户意味着什么」\n"
            "- **砍掉多余的**：如果一个步骤不直接创造用户价值，质疑它存在的必要性\n"
            "- **体验标准**：验收标准必须包含用户体验维度\n"
            "- **简洁方案**：如果需要解释为什么这么做，说明方案还不够简洁\n"
            "- **品味把关**：丑的方案宁可不做也不将就"
        ),
        "torvalds": (
            "你不是那种画 UML 图纸上谈兵的架构师：\n"
            "- **从代码出发**：先读现有代码，理解真实约束，然后才规划。不读代码就规划的人是白痴\n"
            "- **简单方案优先**：如果需要 5 步，先问有没有 2 步的办法\n"
            "- **抽象要准确**：错误的抽象比没有抽象更糟糕\n"
            "- **依赖关系图**：脑中永远有模块依赖图，确保不引入循环依赖\n"
            "- **可并行的就并行**：能同时开工的步骤一定标出来"
        ),
        "rams": (
            "你从设计的视角审视计划：\n"
            "- **Less but better**：步骤越少越好，每一步都必须有存在的理由\n"
            "- **系统一致性**：计划产出的各部分必须在视觉和交互上统一\n"
            "- **用户动线**：计划必须考虑用户如何一步步使用产品\n"
            "- **十诫检查**：每个步骤都过一遍设计十诫"
        ),
    }

    behavior = persona_specific.get(persona.id, (
        "你以自己的专业视角分析任务：\n"
        "- 理解需求，拆解为可执行步骤\n"
        "- 识别风险和依赖\n"
        "- 分配合理的角色和资源"
    ))

    output_format = (
        "产出 ExecutionPlan，包含：\n"
        "1. 任务分析（理解了什么、关键挑战是什么）\n"
        "2. 步骤列表（每步：描述 + 负责人 + 可并行标记 + 依赖关系）\n"
        "3. 风险识别（可能出问题的地方）\n"
        "4. 验收标准（怎样算完成）"
    )

    tool_rules = (
        "只读：Read、Grep、Glob、Bash（只读命令）\n"
        "不可写：代码文件（你现在是 planning，不是 coding）"
    )

    return behavior, output_format, tool_rules


def _coding_behavior(persona: Persona) -> tuple[str, str, str]:
    """Generate coding specialty behavior."""
    persona_specific = {
        "torvalds": (
            "现在是动手的时候了：\n"
            "- **代码即表达**：变量名就是文档，注释是给不理解设计的人看的\n"
            "- **实现必须简约**：走正确的路，不走捷径。禁止 workaround\n"
            "- **禁止偷懒**：不硬编码、不 copy-paste、不跳过边界条件\n"
            "- **一次做对**：写之前想清楚，很少需要大改第二遍\n"
            "- **性能天然好**：一开始就选对数据结构和算法"
        ),
        "beck": (
            "写代码的方式是 TDD：\n"
            "- **先写测试**：在写实现之前，先写一个会失败的测试\n"
            "- **最小实现**：只写刚好让测试通过的代码\n"
            "- **重构**：绿了之后重构，保持代码干净\n"
            "- **YAGNI**：不写用不到的代码\n"
            "- **小步前进**：每次改动都很小，随时可以回退"
        ),
    }

    behavior = persona_specific.get(persona.id, (
        "按计划执行编码任务：\n"
        "- 严格按 plan step 执行\n"
        "- 处理所有边界条件\n"
        "- 代码清晰可读"
    ))

    output_format = (
        "代码变更完成后，输出：\n"
        "1. 改动摘要（改了哪些文件、为什么）\n"
        "2. 关键设计决策\n"
        "3. 需要注意的边界条件"
    )

    tool_rules = "全部工具（在 worktree 内）"

    return behavior, output_format, tool_rules


def _review_behavior(persona: Persona) -> tuple[str, str, str]:
    """Generate review specialty behavior."""
    persona_specific = {
        "martin": (
            "你的代码审查如同外科手术般精确：\n"
            "- **SOLID 原则**：逐条检查，违反即扣分\n"
            "- **命名检查**：每个变量、函数、类的命名是否清晰表达意图\n"
            "- **函数长度**：超过 20 行的函数要质疑\n"
            "- **单一职责**：一个函数只做一件事\n"
            "- **代码异味**：重复代码、过长参数列表、特性嫉妒...\n"
            "- **教练心态**：每个扣分都解释为什么，并给出改进建议"
        ),
        "torvalds": (
            "你的 review 风格在 Linux 内核社区是传奇：\n"
            "- **架构优先**：先看整体设计，再看细节。局部精巧弥补不了架构的失败\n"
            "- **性能嗅觉**：不必要的内存分配、隐藏的 O(n²)、锁范围过大——一眼看到\n"
            "- **简单即正确**：patch 太复杂，多半方向错了\n"
            "- **毒舌回复**：\"这TM是什么鬼\" 是正常的 review 评语\n"
            "- **但有道理**：每句批评都有技术依据"
        ),
        "rams": (
            "你从设计视角审查：\n"
            "- **视觉一致性**：整个系统的视觉语言是否统一\n"
            "- **交互合理性**：用户操作是否自然、符合直觉\n"
            "- **Less but better**：是否有多余的 UI 元素"
        ),
    }

    behavior = persona_specific.get(persona.id, (
        "按审查标准逐项检查：\n"
        "- 架构合理性\n"
        "- 代码质量\n"
        "- 正确性"
    ))

    output_format = (
        "审查报告：\n"
        "1. 评分（10 分制，≥9 通过）\n"
        "2. 逐项分析\n"
        "3. 问题清单（如有）\n"
        "4. 改进建议\n"
        "5. pass/fail 结论 + 理由"
    )

    tool_rules = "只读：Read、Grep、Glob、Bash（只读命令）"

    return behavior, output_format, tool_rules


def _testing_behavior(persona: Persona) -> tuple[str, str, str]:
    """Generate testing specialty behavior."""
    behavior = (
        "你是测试的化身：\n"
        "- **核心逻辑覆盖**：先测试最重要的功能路径\n"
        "- **边界条件猎手**：空值、零值、极大值、类型错误、并发\n"
        "- **先写复现测试**：发现 bug 先写能复现的测试用例\n"
        "- **红绿循环**：确认测试在修复前确实失败\n"
        "- **回归保护**：确保修复不破坏已有功能"
    )

    output_format = (
        "测试报告：\n"
        "1. 测试用例列表（每个：描述 + 预期 + 实际 + pass/fail）\n"
        "2. 覆盖范围总结\n"
        "3. 发现的 bug（如有：严重程度 + 复现步骤）\n"
        "4. 总体 pass/fail 结论"
    )

    tool_rules = "只读 + 可执行测试命令"

    return behavior, output_format, tool_rules


def _discussion_behavior(persona: Persona) -> tuple[str, str, str]:
    """Generate discussion specialty behavior."""
    behavior = (
        "你参与建设性对抗讨论：\n"
        "- **有立场**：不做和事佬，说出你真正的看法\n"
        "- **有依据**：每个观点都有技术或产品层面的支撑\n"
        "- **有结论**：讨论必须产出可执行的决策\n"
        "- **尊重分歧**：记录不同意的理由，但服从最终决策"
    )

    output_format = (
        "讨论结论：\n"
        "1. 核心议题\n"
        "2. 各方观点摘要\n"
        "3. 最终决策\n"
        "4. 决策依据"
    )

    tool_rules = "只读 + 可写共享记忆"

    return behavior, output_format, tool_rules


# Specialty → behavior generator mapping
_BEHAVIOR_GENERATORS: dict[Specialty, Any] = {
    "planning": _planning_behavior,
    "coding": _coding_behavior,
    "review": _review_behavior,
    "testing": _testing_behavior,
    "discussion": _discussion_behavior,
}


# ── Main Generator ─────────────────────────────────────────────────────

def build_actor_prompt(
    persona: Persona,
    specialty: Specialty,
    task_context: dict[str, str],
    personas_dir: Path,
) -> str:
    """Generate complete CLAUDE.md for a persona × specialty actor.

    Three-section composition:
      1. Persona base (from .md file)
      2. Specialty behavior (personalized per persona)
      3. Task context (dynamic injection)

    Args:
        persona: The persona definition.
        specialty: The specialty this actor performs.
        task_context: Dynamic context dict with keys like:
            - "task_description": What the task is about
            - "memory_path": Path to shared memory file
            - "plan_path": Path to plan.json (planning actors)
            - "worktree_path": Path to code worktree (coding actors)
            - "review_target": What to review (review actors)
            - "assigned_step": The plan step being executed
        personas_dir: Directory containing persona .md files.

    Returns:
        Complete system prompt string.
    """
    # Section 1: Persona base
    persona_base = persona.load_base(personas_dir)

    # Section 2: Specialty behavior
    display_name = SPECIALTY_DISPLAY.get(specialty, specialty)
    thinking_mode = SPECIALTY_THINKING.get(specialty, "convergent")
    thinking_label = "发散思维" if thinking_mode == "divergent" else "收敛执行"

    generator = _BEHAVIOR_GENERATORS.get(specialty)
    if generator is None:
        raise ValueError(f"No behavior generator for specialty: {specialty}")

    behavior, output_format, tool_rules = generator(persona)

    # Section 3: Task context
    context_lines = []
    ctx_mapping = [
        ("task_description", "任务描述"),
        ("assigned_step", "执行步骤"),
        ("review_target", "审查目标"),
        ("memory_path", "共享记忆"),
        ("plan_path", "计划文件"),
        ("worktree_path", "代码工作目录"),
    ]
    for key, label in ctx_mapping:
        if key in task_context and task_context[key]:
            context_lines.append(f"- {label}：{task_context[key]}")

    context_section = "\n".join(context_lines) if context_lines else "- 无额外上下文"

    # Assemble
    prompt = f"""# 你是 {persona.name} — 此刻你在做 {display_name}

{persona_base}

## 作为 {display_name} 的你（{thinking_label}）
{behavior}

## 输出要求
{output_format}

## 工具使用
{tool_rules}

## Task 上下文
{context_section}"""

    return prompt.strip()


def build_triage_prompt(task_description: str) -> str:
    """Build the triage prompt for Phase 0.

    The triage is done by the orchestrator itself, not by an actor.
    Returns a system prompt that asks Claude to classify task complexity.
    """
    return f"""你是 Conductor 编排引擎的分诊模块。分析以下任务，判断其复杂度。

## 任务描述
{task_description}

## 判断标准

**TRIVIAL（一步完成）**：
- 任务描述少于 2 句话
- 明确指向单个文件/单个函数的修改
- 不涉及架构变化、不涉及多文件联动

**SMALL（明确任务，不需要讨论）**：
- 任务目标清晰，不需要讨论方向
- 可能涉及多个文件，但变更模式明确
- 不需要先出设计方案

**COMPLEX（需要发散讨论/多视角/设计先行）**：
- 任务描述模糊或有多种理解方式
- 涉及架构决策、技术选型、用户体验取舍
- 需要多个角色的视角碰撞才能确定方向
- 涉及 UI/前端时通常需要先 design

请输出你的判断。"""
