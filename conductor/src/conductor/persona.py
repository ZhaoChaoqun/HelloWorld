"""Persona definitions for Dev scenario.

Each Persona has a base personality and supported specialties.
The persona base text is loaded from personas/*.md files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ThinkingMode = Literal["divergent", "convergent"]
Specialty = Literal["planning", "discussion", "coding", "review", "testing", "design"]

# Specialty → thinking mode mapping
SPECIALTY_THINKING: dict[Specialty, ThinkingMode] = {
    "planning": "divergent",
    "discussion": "divergent",
    "coding": "convergent",
    "review": "convergent",
    "testing": "convergent",
    "design": "convergent",
}

# Specialty display names (Chinese)
SPECIALTY_DISPLAY: dict[Specialty, str] = {
    "planning": "Planning（规划）",
    "discussion": "Discussion（讨论）",
    "coding": "Coding（编码）",
    "review": "Review（审查）",
    "testing": "Testing（测试）",
    "design": "Design（设计）",
}


@dataclass(frozen=True)
class Persona:
    """A persona definition for the Dev scenario."""

    id: str
    name: str
    specialties: tuple[Specialty, ...]
    tags: tuple[str, ...]

    def supports(self, specialty: Specialty) -> bool:
        return specialty in self.specialties

    def load_base(self, personas_dir: Path) -> str:
        """Load persona base text from markdown file."""
        path = personas_dir / f"{self.id}.md"
        if not path.exists():
            raise FileNotFoundError(f"Persona base file not found: {path}")
        return path.read_text(encoding="utf-8").strip()


# ── Dev Scenario Persona Pool ──────────────────────────────────────────

JOBS = Persona(
    id="jobs",
    name="Steve Jobs",
    specialties=("planning", "review", "discussion"),
    tags=("product", "ux", "strategy"),
)

TORVALDS = Persona(
    id="torvalds",
    name="Linus Torvalds",
    specialties=("planning", "coding", "review", "discussion"),
    tags=("architecture", "backend", "performance"),
)

MARTIN = Persona(
    id="martin",
    name="Robert C. Martin",
    specialties=("review",),
    tags=("clean-code", "solid", "refactoring"),
)

BECK = Persona(
    id="beck",
    name="Kent Beck",
    specialties=("testing", "coding"),
    tags=("tdd", "agile", "xp"),
)

RAMS = Persona(
    id="rams",
    name="Dieter Rams",
    specialties=("planning", "review", "design"),
    tags=("ux", "interaction", "visual"),
)

DEV_PERSONAS: dict[str, Persona] = {
    p.id: p for p in [JOBS, TORVALDS, MARTIN, BECK, RAMS]
}


def get_persona(persona_id: str) -> Persona:
    """Get a persona by ID. Raises KeyError if not found."""
    if persona_id not in DEV_PERSONAS:
        raise KeyError(
            f"Unknown persona '{persona_id}'. "
            f"Available: {', '.join(DEV_PERSONAS.keys())}"
        )
    return DEV_PERSONAS[persona_id]


def get_personas_for_specialty(specialty: Specialty) -> list[Persona]:
    """Get all personas that support a given specialty."""
    return [p for p in DEV_PERSONAS.values() if p.supports(specialty)]
