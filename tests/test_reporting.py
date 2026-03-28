import unittest

from deletebench.reporting import format_summary, summarize_results


class ReportingTests(unittest.TestCase):
    def test_summarize_empty_results(self) -> None:
        summary = summarize_results([])
        self.assertEqual(summary["run_count"], 0)
        self.assertEqual(summary["average_total_score"], 0.0)
        self.assertEqual(summary["by_mode"], {})

    def test_format_summary_includes_breakdowns(self) -> None:
        summary = {
            "run_count": 2,
            "average_total_score": 75.0,
            "by_mode": {"pure_deletion": 80.0},
            "by_category": {"ui_only_removal": 75.0},
            "failure_tags": {"under_deletion": 1},
        }
        text = format_summary(summary)
        self.assertIn("Runs: 2", text)
        self.assertIn("pure_deletion", text)
        self.assertIn("ui_only_removal", text)
        self.assertIn("under_deletion", text)


if __name__ == "__main__":
    unittest.main()
