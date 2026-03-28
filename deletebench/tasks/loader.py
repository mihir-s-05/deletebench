from __future__ import annotations

import json
from pathlib import Path

from deletebench.tasks.schemas import Task, manifest_from_dict


DEFAULT_TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def resolve_tasks_root(tasks_root: str | Path | None = None) -> Path:
    return Path(tasks_root) if tasks_root is not None else DEFAULT_TASKS_ROOT


def load_task(task_id: str, tasks_root: str | Path | None = None) -> Task:
    root = resolve_tasks_root(tasks_root)
    task_path = root / task_id
    manifest_path = task_path / "task.json"
    prompt_path = task_path / "public_prompt.txt"
    repo_path = task_path / "repo"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Task manifest not found: {manifest_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Task prompt not found: {prompt_path}")
    if not repo_path.exists():
        raise FileNotFoundError(f"Task repository not found: {repo_path}")

    manifest = manifest_from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    return Task(
        task_id=manifest.task_id,
        repo_path=repo_path,
        prompt=prompt,
        manifest=manifest,
        task_path=task_path,
    )


def load_tasks(tasks_root: str | Path | None = None) -> list[Task]:
    root = resolve_tasks_root(tasks_root)
    if not root.exists():
        return []

    tasks: list[Task] = []
    for manifest_path in sorted(root.glob("*/task.json")):
        task_id = manifest_path.parent.name
        tasks.append(load_task(task_id, root))
    return tasks
