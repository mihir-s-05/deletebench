import json
import tempfile
import unittest
from pathlib import Path

from deletebench.evaluator import run_hidden_eval
from deletebench.tasks.generator import generate_tasks
from deletebench.tasks.loader import load_task, validate_tasks


class EvaluatorAndValidationTests(unittest.TestCase):
    def test_hidden_eval_invalid_json_returns_failure_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            generate_tasks(tasks_root, force=True)
            task = load_task("deletebench_001", tasks_root)
            task.eval_script_path.write_text("print('not json')\n", encoding="utf-8")

            probes, result = run_hidden_eval(task, task.repo_path)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(len(probes), 1)
            self.assertEqual(probes[0].probe_id, "hidden_eval_invalid_output")
            self.assertFalse(probes[0].passed)

    def test_missing_hidden_eval_script_returns_failure_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            generate_tasks(tasks_root, force=True)
            task = load_task("deletebench_001", tasks_root)
            task.eval_script_path.unlink()

            probes, result = run_hidden_eval(task, task.repo_path)

            self.assertEqual(result.returncode, 1)
            self.assertEqual(probes[0].probe_id, "hidden_eval_script_missing")
            self.assertFalse(probes[0].passed)

    def test_validate_tasks_reports_missing_probe_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            generate_tasks(tasks_root, force=True)
            manifest_path = tasks_root / "deletebench_001" / "task.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["hidden_eval"]["regression_probes"] = []
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

            results = validate_tasks(tasks_root)

            self.assertIn("deletebench_001", results)
            self.assertTrue(any("regression_probes" in error for error in results["deletebench_001"]))

    def test_load_task_raises_on_missing_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tasks_root = Path(tmp_dir) / "tasks"
            generate_tasks(tasks_root, force=True)
            prompt_path = tasks_root / "deletebench_001" / "public_prompt.txt"
            prompt_path.unlink()

            with self.assertRaises(FileNotFoundError):
                load_task("deletebench_001", tasks_root)


if __name__ == "__main__":
    unittest.main()
