"""Decision 20: evaluation cases as data files, grouped by category directory.

A case names a scenario, a planner, a script of steps to drive
`MissionSession` through, and expectations written independently of
planner output (a reason code the case must observe, a violation
ceiling). The directory name under `amis/data/evaluation/` is the
case's category (smoke, constraint, event_response, orbital_window,
explanation, planner_comparison, determinism).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CASES_ROOT = Path(__file__).resolve().parent.parent / "data" / "evaluation"


@dataclass(frozen=True)
class EvaluationCase:
    id: str
    category: str
    scenario: str
    planner: str = "greedy"
    steps: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    expect: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(category: str, data: dict[str, Any]) -> "EvaluationCase":
        return EvaluationCase(
            id=data["id"],
            category=category,
            scenario=data["scenario"],
            planner=data.get("planner", "greedy"),
            steps=tuple(data.get("steps", ())),
            expect=data.get("expect", {}),
        )


def load_cases(root: Path = CASES_ROOT) -> list[EvaluationCase]:
    if not root.exists():
        return []
    cases = []
    for category_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for case_file in sorted(category_dir.glob("*.json")):
            data = json.loads(case_file.read_text())
            cases.append(EvaluationCase.from_dict(category_dir.name, data))
    return cases
