import json
import tempfile
import unittest
from pathlib import Path

from deletebench.reporting import summarize_results
from deletebench.runner import run_task
from deletebench.tasks.generator import generate_tasks
from deletebench.tasks.loader import load_task, load_tasks, validate_tasks


class GeneratorAndRunnerTests(unittest.TestCase):
    def test_generate_v0_suite_has_expected_category_mix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            generated = generate_tasks(tmp_dir, force=True)
            self.assertEqual(len(generated), 12)

            tasks = load_tasks(tmp_dir)
            counts: dict[str, int] = {}
            for task in tasks:
                counts[task.manifest.category] = counts.get(task.manifest.category, 0) + 1

            self.assertEqual(counts["ui_only_removal"], 3)
            self.assertEqual(counts["full_stack_feature_removal"], 3)
            self.assertEqual(counts["feature_flag_sunset"], 2)
            self.assertEqual(counts["shared_abstraction_pruning"], 2)
            self.assertEqual(counts["legacy_path_cleanup"], 2)

    def test_reference_agent_scores_full_credit_and_noop_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = f"{tmp_dir}/tasks"
            results_root = f"{tmp_dir}/results"
            generate_tasks(tasks_root, force=True)

            reference = run_task(
                "deletebench_004",
                tasks_root=tasks_root,
                model_id="reference",
                output_dir=results_root,
            )["evaluation"]
            noop = run_task(
                "deletebench_004",
                tasks_root=tasks_root,
                model_id="noop",
                output_dir=results_root,
            )["evaluation"]

            self.assertEqual(reference.total_score, 100.0)
            self.assertEqual(reference.failure_tags, [])
            self.assertLess(noop.total_score, 100.0)
            self.assertIn("under_deletion", noop.failure_tags)

            summary = summarize_results([reference, noop])
            self.assertEqual(summary["run_count"], 2)
            self.assertLess(summary["average_total_score"], 100.0)

    def test_validate_tasks_reports_generated_suite_as_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            generate_tasks(tmp_dir, force=True)
            results = validate_tasks(tmp_dir)
            self.assertTrue(results)
            self.assertTrue(all(not errors for errors in results.values()))

    def test_command_agent_can_edit_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = f"{tmp_dir}/tasks"
            results_root = f"{tmp_dir}/results"
            generate_tasks(tasks_root, force=True)
            command = (
                "python3 - <<'PY'\n"
                "from pathlib import Path\n"
                "import json\n"
                "import os\n"
                "workspace = Path(os.environ['DELETEBENCH_WORKSPACE'])\n"
                "payload = json.loads((Path(os.environ['DELETEBENCH_TASK_PATH']) / 'hidden_eval' / 'reference_solution.json').read_text())\n"
                "files = payload['files']\n"
                "for path in sorted(workspace.rglob('*'), reverse=True):\n"
                "    if path.is_file():\n"
                "        rel = path.relative_to(workspace)\n"
                "        if str(rel) not in files:\n"
                "            path.unlink()\n"
                "for rel, content in files.items():\n"
                "    target = workspace / rel\n"
                "    target.parent.mkdir(parents=True, exist_ok=True)\n"
                "    target.write_text(content, encoding='utf-8')\n"
                "PY"
            )
            evaluation = run_task(
                "deletebench_001",
                tasks_root=tasks_root,
                model_id="command",
                agent_command=command,
                output_dir=results_root,
            )["evaluation"]
            self.assertEqual(evaluation.total_score, 100.0)

    def test_missing_hidden_eval_script_is_reported_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            results_root = Path(tmp_dir) / "results"
            generate_tasks(tasks_root, force=True)
            task = load_task("deletebench_001", tasks_root)
            (tasks_root / "deletebench_001" / "hidden_eval" / "eval.py").unlink()
            record = run_task(task, output_dir=results_root)
            probe_ids = {probe.probe_id for probe in record["evaluation"].probes}
            self.assertIn("hidden_eval_script_missing", probe_ids)

    def test_invalid_hidden_eval_json_becomes_failed_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            results_root = Path(tmp_dir) / "results"
            generate_tasks(tasks_root, force=True)
            eval_path = tasks_root / "deletebench_001" / "hidden_eval" / "eval.py"
            eval_path.write_text("print('not json')\n", encoding="utf-8")
            task = load_task("deletebench_001", tasks_root)
            record = run_task(task, output_dir=results_root)
            probe_ids = {probe.probe_id for probe in record["evaluation"].probes}
            self.assertIn("hidden_eval_invalid_output", probe_ids)

    def test_loader_rejects_invalid_task_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            task_dir = root / "broken_task"
            (task_dir / "repo").mkdir(parents=True)
            (task_dir / "public_prompt.txt").write_text("broken\n", encoding="utf-8")
            (task_dir / "task.json").write_text(
                json.dumps(
                    {
                        "task_id": "broken_task",
                        "repo_name": "broken",
                        "entry_commit": "generated",
                        "mode": "pure_deletion",
                        "category": "ui_only_removal",
                        "difficulty": "easy",
                        "instruction": "broken",
                        "hidden_eval": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_task("broken_task", root)


if __name__ == "__main__":
    unittest.main()
