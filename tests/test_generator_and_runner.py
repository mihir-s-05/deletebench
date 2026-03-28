import tempfile
import unittest

from deletebench.reporting import summarize_results
from deletebench.runner import run_task
from deletebench.tasks.generator import generate_tasks
from deletebench.tasks.loader import load_tasks


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


if __name__ == "__main__":
    unittest.main()
