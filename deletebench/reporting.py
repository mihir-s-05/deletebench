from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from deletebench.tasks.schemas import EvaluationResult


def load_result_payloads(results_dir: str | Path) -> list[dict[str, object]]:
    root = Path(results_dir)
    payloads: list[dict[str, object]] = []
    if not root.exists():
        return payloads
    for evaluation_path in sorted(root.rglob("evaluation.json")):
        payloads.append(json.loads(evaluation_path.read_text(encoding="utf-8")))
    return payloads


def summarize_results(results: Iterable[EvaluationResult | dict[str, object]]) -> dict[str, object]:
    payloads: list[dict[str, object]] = []
    for result in results:
        if isinstance(result, EvaluationResult):
            payloads.append(result.to_dict())
        else:
            payloads.append(result)

    if not payloads:
        return {
            "run_count": 0,
            "average_total_score": 0.0,
            "by_mode": {},
            "by_category": {},
            "failure_tags": {},
        }

    total_scores: list[float] = []
    mode_scores: dict[str, list[float]] = defaultdict(list)
    category_scores: dict[str, list[float]] = defaultdict(list)
    failure_tags: Counter[str] = Counter()

    for payload in payloads:
        metadata = payload.get("metadata", {})
        score = float(payload.get("total_score", 0.0))
        total_scores.append(score)
        mode_scores[str(metadata.get("mode", "unknown"))].append(score)
        category_scores[str(metadata.get("category", "unknown"))].append(score)
        for tag in payload.get("failure_tags", []):
            failure_tags[str(tag)] += 1

    def average(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    return {
        "run_count": len(payloads),
        "average_total_score": average(total_scores),
        "by_mode": {key: average(value) for key, value in sorted(mode_scores.items())},
        "by_category": {
            key: average(value) for key, value in sorted(category_scores.items())
        },
        "failure_tags": dict(sorted(failure_tags.items())),
    }


def format_summary(summary: dict[str, object]) -> str:
    lines = [
        f"Runs: {summary['run_count']}",
        f"Average total score: {summary['average_total_score']}",
    ]

    by_mode = summary.get("by_mode", {})
    if by_mode:
        lines.append("By mode:")
        for mode, score in by_mode.items():
            lines.append(f"  - {mode}: {score}")

    by_category = summary.get("by_category", {})
    if by_category:
        lines.append("By category:")
        for category, score in by_category.items():
            lines.append(f"  - {category}: {score}")

    failure_tags = summary.get("failure_tags", {})
    if failure_tags:
        lines.append("Failure tags:")
        for tag, count in failure_tags.items():
            lines.append(f"  - {tag}: {count}")

    return "\n".join(lines)
