from __future__ import annotations

import json
from pathlib import Path

from deletebench.tasks.schemas import REQUIRED_EVALUATION_CATEGORIES, Task, manifest_from_dict


DEFAULT_TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def _load_checks_payload(task: Task) -> dict[str, object]:
    checks_path = task.task_path / "hidden_eval" / "checks.json"
    return json.loads(checks_path.read_text(encoding="utf-8"))


def resolve_tasks_root(tasks_root: str | Path | None = None) -> Path:
    return Path(tasks_root) if tasks_root is not None else DEFAULT_TASKS_ROOT


def validate_task(task: Task) -> list[str]:
    errors: list[str] = []

    if not task.prompt.strip():
        errors.append("public prompt must not be empty")
    if not task.eval_script_path.exists():
        errors.append(f"hidden eval script missing: {task.eval_script_path}")
    if not task.residue_rules_path.exists():
        errors.append(f"residue rules missing: {task.residue_rules_path}")
    if not task.reference_solution_path.exists():
        errors.append(f"reference solution missing: {task.reference_solution_path}")
    if not task.manifest.hidden_eval.commands:
        errors.append("hidden_eval.commands must define at least one command")
    if task.manifest.hidden_eval.install and "install" not in task.manifest.hidden_eval.commands:
        errors.append("hidden_eval.install is true but no install command is defined")
    if not task.manifest.hidden_eval.removal_probes:
        errors.append("hidden_eval.removal_probes must contain at least one probe id")
    if not task.manifest.hidden_eval.regression_probes:
        errors.append("hidden_eval.regression_probes must contain at least one probe id")
    if not task.manifest.hidden_eval.residue_checks:
        errors.append("hidden_eval.residue_checks must contain at least one residue rule group")
    if not any(
        key in task.manifest.hidden_eval.extra
        for key in ("max_files_changed", "max_added_lines", "max_touched_directories")
    ):
        errors.append(
            "task must define at least one task-authored diff_hygiene budget "
            "(max_files_changed, max_added_lines, or max_touched_directories)"
        )

    required_weight_categories = set(task.manifest.component_weights)
    missing_categories = REQUIRED_EVALUATION_CATEGORIES - required_weight_categories
    if missing_categories:
        errors.append(
            f"component weights are missing required categories: {sorted(missing_categories)}"
        )

    if task.eval_script_path.exists():
        checks_path = task.task_path / "hidden_eval" / "checks.json"
        if not checks_path.exists():
            errors.append(f"hidden eval checks missing: {checks_path}")
        else:
            try:
                payload = _load_checks_payload(task)
            except json.JSONDecodeError as exc:
                errors.append(f"hidden eval checks are invalid JSON: {exc}")
            else:
                probes = payload.get("probes")
                if not isinstance(probes, list):
                    errors.append("hidden eval checks payload must contain a probes list")
                else:
                    probe_ids: set[str] = set()
                    categories: set[str] = set()
                    for probe in probes:
                        if not isinstance(probe, dict):
                            errors.append("hidden eval checks must contain only object probes")
                            continue
                        probe_id = probe.get("probe_id")
                        category = probe.get("category")
                        if not probe_id:
                            errors.append("hidden eval probe is missing probe_id")
                            continue
                        probe_ids.add(str(probe_id))
                        if category:
                            categories.add(str(category))

                    missing_removal = sorted(set(task.manifest.hidden_eval.removal_probes) - probe_ids)
                    if missing_removal:
                        errors.append(
                            f"declared removal probes missing from checks.json: {missing_removal}"
                        )
                    missing_regression = sorted(
                        set(task.manifest.hidden_eval.regression_probes) - probe_ids
                    )
                    if missing_regression:
                        errors.append(
                            f"declared regression probes missing from checks.json: {missing_regression}"
                        )
                    if "removal_completeness" not in categories:
                        errors.append("hidden eval checks must include removal_completeness probes")
                    if "regression_safety" not in categories:
                        errors.append("hidden eval checks must include regression_safety probes")

    if task.residue_rules_path.exists():
        try:
            residue_payload = json.loads(task.residue_rules_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"residue rules must be valid JSON in v0: {exc}")
        else:
            if not isinstance(residue_payload, dict):
                errors.append("residue rules must be a JSON object")
            else:
                missing_residue_groups = sorted(
                    set(task.manifest.hidden_eval.residue_checks) - set(residue_payload)
                )
                if missing_residue_groups:
                    errors.append(
                        f"declared residue rule groups missing from residue rules: {missing_residue_groups}"
                    )

    return errors


def load_task(
    task_id: str,
    tasks_root: str | Path | None = None,
    *,
    validate: bool = True,
) -> Task:
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
    task = Task(
        task_id=manifest.task_id,
        repo_path=repo_path,
        prompt=prompt,
        manifest=manifest,
        task_path=task_path,
    )
    errors = validate_task(task) if validate else []
    if validate and errors:
        raise ValueError(f"Task {task.task_id} is invalid: {'; '.join(errors)}")
    return task


def load_tasks(tasks_root: str | Path | None = None, *, validate: bool = True) -> list[Task]:
    root = resolve_tasks_root(tasks_root)
    if not root.exists():
        return []

    tasks: list[Task] = []
    for manifest_path in sorted(root.glob("*/task.json")):
        task_id = manifest_path.parent.name
        tasks.append(load_task(task_id, root, validate=validate))
    return tasks


def validate_tasks(tasks_root: str | Path | None = None) -> dict[str, list[str]]:
    root = resolve_tasks_root(tasks_root)
    if not root.exists():
        return {}

    results: dict[str, list[str]] = {}
    for manifest_path in sorted(root.glob("*/task.json")):
        task_id = manifest_path.parent.name
        try:
            task = load_task(task_id, root, validate=False)
        except Exception as exc:  # pragma: no cover - defensive path
            results[task_id] = [str(exc)]
            continue
        results[task_id] = validate_task(task)
    return results
