from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from deletebench.tasks.schemas import EvaluationResult, ProbeResult, Task


def score_probe_results(
    task: Task,
    probes: Iterable[ProbeResult],
    *,
    metadata: dict[str, object] | None = None,
) -> EvaluationResult:
    probe_list = list(probes)
    passed_weights: dict[str, float] = defaultdict(float)
    total_weights: dict[str, float] = defaultdict(float)
    failure_tags: set[str] = set()

    for probe in probe_list:
        total_weights[probe.category] += probe.weight
        if probe.passed:
            passed_weights[probe.category] += probe.weight
        else:
            failure_tags.update(probe.failure_tags)

    sub_scores: dict[str, float] = {}
    for category, component_weight in task.manifest.component_weights.items():
        total_weight = total_weights.get(category, 0.0)
        if total_weight == 0:
            sub_scores[category] = 0.0
            continue
        sub_scores[category] = round(
            component_weight * (passed_weights.get(category, 0.0) / total_weight),
            2,
        )

    return EvaluationResult(
        task_id=task.task_id,
        total_score=round(sum(sub_scores.values()), 2),
        sub_scores=sub_scores,
        probes=probe_list,
        failure_tags=sorted(failure_tags),
        metadata=dict(metadata or {}),
    )
