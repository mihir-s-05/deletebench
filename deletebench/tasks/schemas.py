from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_COMPONENT_WEIGHTS: dict[str, float] = {
    "removal_completeness": 35.0,
    "regression_safety": 25.0,
    "residue_cleanup": 20.0,
    "diff_hygiene": 10.0,
    "spec_compliance": 10.0,
}

REQUIRED_EVALUATION_CATEGORIES = frozenset(DEFAULT_COMPONENT_WEIGHTS)


@dataclass(slots=True)
class ProbeResult:
    probe_id: str
    passed: bool
    category: str
    message: str
    weight: float = 1.0
    failure_tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentResult:
    final_repo_path: str
    diff_text: str
    runtime_seconds: float
    files_changed: list[str]
    logs_path: str
    model_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvaluationResult:
    task_id: str
    total_score: float
    sub_scores: dict[str, float]
    probes: list[ProbeResult]
    failure_tags: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["probes"] = [probe.to_dict() for probe in self.probes]
        return payload


@dataclass(slots=True)
class HiddenEvalSpec:
    commands: dict[str, str] = field(default_factory=dict)
    removal_probes: list[str] = field(default_factory=list)
    regression_probes: list[str] = field(default_factory=list)
    residue_checks: list[str] = field(default_factory=list)
    weights: dict[str, float] = field(default_factory=dict)
    eval_script: str = "hidden_eval/eval.py"
    residue_rules: str = "hidden_eval/residue_rules.yaml"
    install: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        extras = payload.pop("extra")
        payload.update(extras)
        return payload


@dataclass(slots=True)
class TaskManifest:
    task_id: str
    repo_name: str
    entry_commit: str
    mode: str
    category: str
    difficulty: str
    instruction: str
    public_metadata: dict[str, Any] = field(default_factory=dict)
    hidden_eval: HiddenEvalSpec = field(default_factory=HiddenEvalSpec)

    @property
    def component_weights(self) -> dict[str, float]:
        weights = dict(DEFAULT_COMPONENT_WEIGHTS)
        weights.update(self.hidden_eval.weights)
        return weights

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hidden_eval"] = self.hidden_eval.to_dict()
        return payload


@dataclass(slots=True)
class Task:
    task_id: str
    repo_path: Path
    prompt: str
    manifest: TaskManifest
    task_path: Path

    @property
    def eval_script_path(self) -> Path:
        return self.task_path / self.manifest.hidden_eval.eval_script

    @property
    def residue_rules_path(self) -> Path:
        return self.task_path / self.manifest.hidden_eval.residue_rules

    @property
    def reference_solution_path(self) -> Path:
        reference_name = self.manifest.hidden_eval.extra.get(
            "reference_solution",
            "hidden_eval/reference_solution.json",
        )
        return self.task_path / reference_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "repo_path": str(self.repo_path),
            "prompt": self.prompt,
            "manifest": self.manifest.to_dict(),
            "task_path": str(self.task_path),
        }


def _coerce_hidden_eval(data: dict[str, Any]) -> HiddenEvalSpec:
    known_fields = {
        "commands",
        "removal_probes",
        "regression_probes",
        "residue_checks",
        "weights",
        "eval_script",
        "residue_rules",
        "install",
    }
    extra = {key: value for key, value in data.items() if key not in known_fields}
    return HiddenEvalSpec(
        commands=dict(data.get("commands", {})),
        removal_probes=list(data.get("removal_probes", [])),
        regression_probes=list(data.get("regression_probes", [])),
        residue_checks=list(data.get("residue_checks", [])),
        weights=dict(data.get("weights", {})),
        eval_script=str(data.get("eval_script", "hidden_eval/eval.py")),
        residue_rules=str(data.get("residue_rules", "hidden_eval/residue_rules.yaml")),
        install=bool(data.get("install", False)),
        extra=extra,
    )


def manifest_from_dict(data: dict[str, Any]) -> TaskManifest:
    required = (
        "task_id",
        "repo_name",
        "entry_commit",
        "mode",
        "category",
        "difficulty",
        "instruction",
    )
    missing = sorted(key for key in required if key not in data)
    if missing:
        raise ValueError(f"Task manifest is missing required fields: {missing}")

    return TaskManifest(
        task_id=str(data["task_id"]),
        repo_name=str(data["repo_name"]),
        entry_commit=str(data["entry_commit"]),
        mode=str(data["mode"]),
        category=str(data["category"]),
        difficulty=str(data["difficulty"]),
        instruction=str(data["instruction"]),
        public_metadata=dict(data.get("public_metadata", {})),
        hidden_eval=_coerce_hidden_eval(dict(data.get("hidden_eval", {}))),
    )
