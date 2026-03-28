from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from deletebench.scoring import score_probe_results
from deletebench.tasks.schemas import AgentResult, ProbeResult, Task
from deletebench.utils.diff_utils import (
    diff_directories,
    diff_snapshots,
    load_reference_snapshot,
    snapshot_directory,
)
from deletebench.utils.residue import load_residue_rules, run_residue_checks
from deletebench.utils.subprocess_utils import CommandResult, run_command


DEFAULT_COMMAND_TIMEOUT = 120


def _command_weight(command_name: str) -> float:
    if command_name == "test":
        return 2.0
    if command_name in {"build", "typecheck", "lint"}:
        return 1.25
    return 1.0


def run_build_checks(task: Task, repo_path: Path) -> tuple[list[ProbeResult], list[dict[str, object]]]:
    probes: list[ProbeResult] = []
    command_payloads: list[dict[str, object]] = []

    for command_name, command in task.manifest.hidden_eval.commands.items():
        result = run_command(command, cwd=repo_path, timeout=DEFAULT_COMMAND_TIMEOUT)
        command_payloads.append({"name": command_name, **result.to_dict()})
        probes.append(
            ProbeResult(
                probe_id=f"{command_name}_command",
                passed=result.succeeded,
                category="regression_safety",
                message=(
                    f"Command {command_name!r} passed."
                    if result.succeeded
                    else f"Command {command_name!r} failed with exit code {result.returncode}."
                ),
                weight=_command_weight(command_name),
                failure_tags=["shared_abstraction_breakage"] if command_name == "test" else ["spec_violation"],
                metadata={"stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]},
            )
        )
    return probes, command_payloads


def run_hidden_eval(task: Task, repo_path: Path) -> tuple[list[ProbeResult], CommandResult]:
    if not task.eval_script_path.exists():
        probe = ProbeResult(
            probe_id="hidden_eval_script_missing",
            passed=False,
            category="spec_compliance",
            message=f"Hidden evaluation script not found: {task.eval_script_path}",
            failure_tags=["spec_violation"],
        )
        return [
            probe
        ], CommandResult(
            command=str(task.eval_script_path),
            cwd=str(task.task_path),
            returncode=1,
            stdout="",
            stderr="missing hidden evaluation script",
            runtime_seconds=0.0,
        )

    result = run_command(
        [sys.executable, str(task.eval_script_path.resolve()), "--repo", str(repo_path.resolve())],
        cwd=task.task_path.resolve(),
        timeout=DEFAULT_COMMAND_TIMEOUT,
    )
    if not result.succeeded:
        probe = ProbeResult(
            probe_id="hidden_eval_execution",
            passed=False,
            category="spec_compliance",
            message="Hidden evaluation script failed to execute.",
            failure_tags=["spec_violation"],
            metadata={"stdout": result.stdout[-1000:], "stderr": result.stderr[-1000:]},
        )
        return [probe], result

    payload = json.loads(result.stdout)
    probes: list[ProbeResult] = []
    for item in payload.get("probes", []):
        probes.append(
            ProbeResult(
                probe_id=str(item["probe_id"]),
                passed=bool(item["passed"]),
                category=str(item["category"]),
                message=str(item["message"]),
                weight=float(item.get("weight", 1.0)),
                failure_tags=[str(tag) for tag in item.get("failure_tags", [])],
                metadata=dict(item.get("metadata", {})),
            )
        )
    return probes, result


def run_spec_compliance_checks(repo_path: Path) -> list[ProbeResult]:
    patterns = [
        (r"Not implemented", "stub_substitution", "Placeholder stubs are not allowed."),
        (r"TODO[^\n]*remove", "spec_violation", "Temporary TODO removals are not allowed."),
        (r"@unittest\.skip|skipTest\(", "spec_violation", "Skipped tests are not allowed as a benchmark dodge."),
        (r"xfail", "spec_violation", "xfail markers are not allowed as a benchmark dodge."),
        (r"deprecat(?:e|ed|ion)", "deprecation_instead_of_deletion", "Deprecation text is not a substitute for deletion."),
    ]

    probes: list[ProbeResult] = []
    text_cache: list[tuple[str, str]] = []
    for file_path in sorted(repo_path.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in file_path.relative_to(repo_path).parts):
            continue
        try:
            text_cache.append((str(file_path.relative_to(repo_path)), file_path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue

    for index, (pattern, failure_tag, description) in enumerate(patterns, start=1):
        regex = re.compile(pattern, re.IGNORECASE)
        matches = [relative_path for relative_path, text in text_cache if regex.search(text)]
        probes.append(
            ProbeResult(
                probe_id=f"spec_pattern_{index}",
                passed=not matches,
                category="spec_compliance",
                message=description if not matches else f"{description} Found matches in {matches[:5]}",
                failure_tags=[failure_tag],
                metadata={"pattern": pattern, "matches": matches[:5]},
            )
        )
    return probes


def run_diff_hygiene_checks(task: Task, baseline_repo_path: Path, final_repo_path: Path) -> tuple[list[ProbeResult], dict[str, object]]:
    candidate_stats = diff_directories(baseline_repo_path, final_repo_path)
    metadata: dict[str, object] = {"candidate_diff": candidate_stats.to_dict()}
    probes: list[ProbeResult] = []

    allowed_touched_files = list(task.manifest.hidden_eval.extra.get("allowed_touched_files", []))
    allowed_set = set(allowed_touched_files)
    touched_slack = int(task.manifest.hidden_eval.extra.get("touched_file_slack", 1))
    outside_files = [path for path in candidate_stats.files_changed if allowed_set and path not in allowed_set]

    probes.append(
        ProbeResult(
            probe_id="diff_no_unrelated_files",
            passed=not outside_files,
            category="diff_hygiene",
            message=(
                "The diff stays within the expected blast radius."
                if not outside_files
                else f"The diff touches unrelated files: {outside_files[:5]}"
            ),
            failure_tags=["unrelated_rewrite"],
            metadata={"outside_files": outside_files[:10], "allowed_touched_files": allowed_touched_files},
        )
    )

    probes.append(
        ProbeResult(
            probe_id="diff_touched_file_budget",
            passed=(len(candidate_stats.files_changed) <= len(allowed_touched_files) + touched_slack) if allowed_touched_files else True,
            category="diff_hygiene",
            message=(
                "Touched file count stays within the expected budget."
                if not allowed_touched_files or len(candidate_stats.files_changed) <= len(allowed_touched_files) + touched_slack
                else f"Touched {len(candidate_stats.files_changed)} files; expected at most {len(allowed_touched_files) + touched_slack}."
            ),
            failure_tags=["unrelated_rewrite"],
            metadata={"touched_files": candidate_stats.files_changed, "budget": len(allowed_touched_files) + touched_slack},
        )
    )

    if task.reference_solution_path.exists():
        reference_snapshot = load_reference_snapshot(task.reference_solution_path)
        reference_stats = diff_snapshots(snapshot_directory(baseline_repo_path), reference_snapshot)
        metadata["reference_diff"] = reference_stats.to_dict()
        added_slack = int(task.manifest.hidden_eval.extra.get("added_lines_slack", 5))
        probes.append(
            ProbeResult(
                probe_id="diff_added_line_budget",
                passed=candidate_stats.added_lines <= reference_stats.added_lines + added_slack,
                category="diff_hygiene",
                message=(
                    "Added line count stays within the expected budget."
                    if candidate_stats.added_lines <= reference_stats.added_lines + added_slack
                    else f"Added {candidate_stats.added_lines} lines; expected at most {reference_stats.added_lines + added_slack}."
                ),
                failure_tags=["unrelated_rewrite"],
                metadata={
                    "candidate_added_lines": candidate_stats.added_lines,
                    "reference_added_lines": reference_stats.added_lines,
                    "budget": reference_stats.added_lines + added_slack,
                },
            )
        )
    else:
        metadata["reference_diff"] = None

    return probes, metadata


def evaluate_task(
    task: Task,
    final_repo_path: str | Path,
    agent_result: AgentResult,
    *,
    baseline_repo_path: str | Path | None = None,
):
    final_repo = Path(final_repo_path)
    baseline_repo = Path(baseline_repo_path) if baseline_repo_path is not None else task.repo_path

    probes: list[ProbeResult] = []
    build_probes, command_payloads = run_build_checks(task, final_repo)
    probes.extend(build_probes)

    hidden_probes, hidden_eval_result = run_hidden_eval(task, final_repo)
    probes.extend(hidden_probes)

    residue_probes = run_residue_checks(final_repo, load_residue_rules(task.residue_rules_path))
    probes.extend(residue_probes)

    spec_probes = run_spec_compliance_checks(final_repo)
    probes.extend(spec_probes)

    diff_probes, diff_metadata = run_diff_hygiene_checks(task, baseline_repo, final_repo)
    probes.extend(diff_probes)

    metadata = {
        "mode": task.manifest.mode,
        "category": task.manifest.category,
        "difficulty": task.manifest.difficulty,
        "model_id": agent_result.model_id,
        "runtime_seconds": agent_result.runtime_seconds,
        "files_changed": agent_result.files_changed,
        "command_results": command_payloads,
        "hidden_eval": hidden_eval_result.to_dict(),
        "diff": diff_metadata,
    }
    return score_probe_results(task, probes, metadata=metadata), metadata
