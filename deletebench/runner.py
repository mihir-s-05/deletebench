from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from deletebench.evaluator import evaluate_task
from deletebench.models.base import resolve_agent
from deletebench.tasks.loader import load_task, load_tasks
from deletebench.tasks.schemas import AgentResult, Task
from deletebench.utils.diff_utils import diff_directories


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def run_task(
    task: Task | str,
    *,
    tasks_root: str | Path | None = None,
    model_id: str = "reference",
    agent_command: str | None = None,
    output_dir: str | Path = "results",
    timeout: int | None = 300,
) -> dict[str, object]:
    task_obj = load_task(task, tasks_root) if isinstance(task, str) else task
    results_root = _ensure_dir(output_dir)
    run_dir = _ensure_dir(results_root / task_obj.task_id / f"{_timestamp()}-{model_id}")
    workspace = run_dir / "workspace"
    shutil.copytree(task_obj.repo_path, workspace)

    agent = resolve_agent(model_id, command=agent_command)
    execution = agent.run(task_obj, workspace, run_dir, timeout=timeout)

    diff_stats = diff_directories(task_obj.repo_path, workspace)
    diff_path = run_dir / "diff.patch"
    diff_path.write_text(diff_stats.diff_text, encoding="utf-8")

    agent_result = AgentResult(
        final_repo_path=str(workspace),
        diff_text=diff_stats.diff_text,
        runtime_seconds=execution.runtime_seconds,
        files_changed=diff_stats.files_changed,
        logs_path=execution.logs_path,
        model_id=execution.model_id,
        metadata=dict(execution.metadata),
    )
    evaluation, _ = evaluate_task(task_obj, workspace, agent_result, baseline_repo_path=task_obj.repo_path)

    (run_dir / "agent_result.json").write_text(
        json.dumps(agent_result.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "evaluation.json").write_text(
        json.dumps(evaluation.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (run_dir / "task.json").write_text(
        json.dumps(task_obj.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return {
        "task": task_obj,
        "agent_result": agent_result,
        "evaluation": evaluation,
        "run_dir": str(run_dir),
    }


def run_suite(
    *,
    tasks_root: str | Path | None = None,
    task_ids: list[str] | None = None,
    model_id: str = "reference",
    agent_command: str | None = None,
    output_dir: str | Path = "results",
    timeout: int | None = 300,
) -> list[dict[str, object]]:
    tasks = load_tasks(tasks_root)
    if task_ids is not None:
        wanted = set(task_ids)
        tasks = [task for task in tasks if task.task_id in wanted]

    results: list[dict[str, object]] = []
    for task in tasks:
        results.append(
            run_task(
                task,
                model_id=model_id,
                agent_command=agent_command,
                output_dir=output_dir,
                timeout=timeout,
            )
        )
    return results
