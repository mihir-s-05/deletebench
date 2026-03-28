from __future__ import annotations

import argparse
import json
from pathlib import Path

from deletebench.reporting import format_summary, load_result_payloads, summarize_results
from deletebench.runner import run_suite, run_task
from deletebench.tasks.generator import generate_tasks
from deletebench.tasks.loader import load_task, load_tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deletebench", description="DeleteBench benchmark harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate-tasks", help="Generate the canonical v0 task set")
    generate_parser.add_argument("--tasks-root", default="tasks")
    generate_parser.add_argument("--force", action="store_true")

    list_parser = subparsers.add_parser("list-tasks", help="List available tasks")
    list_parser.add_argument("--tasks-root", default="tasks")
    list_parser.add_argument("--json", action="store_true")

    show_parser = subparsers.add_parser("show-task", help="Show a task manifest and prompt")
    show_parser.add_argument("task_id")
    show_parser.add_argument("--tasks-root", default="tasks")

    run_task_parser = subparsers.add_parser("run-task", help="Run a single task")
    run_task_parser.add_argument("task_id")
    run_task_parser.add_argument("--tasks-root", default="tasks")
    run_task_parser.add_argument("--agent", default="reference", choices=["reference", "noop", "command"])
    run_task_parser.add_argument("--agent-command", default=None)
    run_task_parser.add_argument("--output-dir", default="results")
    run_task_parser.add_argument("--timeout", type=int, default=300)

    run_suite_parser = subparsers.add_parser("run-suite", help="Run multiple tasks")
    run_suite_parser.add_argument("--tasks-root", default="tasks")
    run_suite_parser.add_argument("--task-id", action="append", dest="task_ids")
    run_suite_parser.add_argument("--agent", default="reference", choices=["reference", "noop", "command"])
    run_suite_parser.add_argument("--agent-command", default=None)
    run_suite_parser.add_argument("--output-dir", default="results")
    run_suite_parser.add_argument("--timeout", type=int, default=300)

    summarize_parser = subparsers.add_parser("summarize", help="Summarize stored evaluation results")
    summarize_parser.add_argument("--results-dir", default="results")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-tasks":
        generated = generate_tasks(Path(args.tasks_root), force=args.force)
        print(f"Generated {len(generated)} tasks under {args.tasks_root}")
        return 0

    if args.command == "list-tasks":
        tasks = load_tasks(args.tasks_root)
        if args.json:
            print(json.dumps([task.to_dict() for task in tasks], indent=2, sort_keys=True))
        else:
            for task in tasks:
                print(f"{task.task_id}: {task.manifest.category} / {task.manifest.mode} / {task.manifest.difficulty}")
        return 0

    if args.command == "show-task":
        task = load_task(args.task_id, args.tasks_root)
        print(json.dumps(task.manifest.to_dict(), indent=2, sort_keys=True))
        print()
        print(task.prompt)
        return 0

    if args.command == "run-task":
        record = run_task(
            args.task_id,
            tasks_root=args.tasks_root,
            model_id=args.agent,
            agent_command=args.agent_command,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
        evaluation = record["evaluation"]
        print(f"Task {evaluation.task_id} scored {evaluation.total_score}")
        print(f"Run directory: {record['run_dir']}")
        return 0

    if args.command == "run-suite":
        records = run_suite(
            tasks_root=args.tasks_root,
            task_ids=args.task_ids,
            model_id=args.agent,
            agent_command=args.agent_command,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
        summary = summarize_results([record["evaluation"] for record in records])
        print(format_summary(summary))
        return 0

    if args.command == "summarize":
        payloads = load_result_payloads(Path(args.results_dir))
        print(format_summary(summarize_results(payloads)))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
