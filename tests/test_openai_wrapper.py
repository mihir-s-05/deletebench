import os
import tempfile
import unittest
from pathlib import Path

from scripts.run_openai_deletebench import apply_edits, build_prompt, collect_workspace_snapshot, FileEdit


class OpenAIWrapperTests(unittest.TestCase):
    def test_collect_snapshot_and_build_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "app").mkdir()
            (root / "app" / "main.py").write_text("print('hi')\n", encoding="utf-8")
            snapshot = collect_workspace_snapshot(root)
            self.assertIn("app/main.py", snapshot)
            prompt = build_prompt("deletebench_001", "Remove feature X", snapshot)
            self.assertIn("TASK ID: deletebench_001", prompt)
            self.assertIn("FILE: app/main.py", prompt)

    def test_apply_edits_writes_and_deletes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "foo.txt"
            target.write_text("old\n", encoding="utf-8")
            apply_edits(
                root,
                [
                    FileEdit(path="foo.txt", action="write", content="new\n"),
                    FileEdit(path="bar.txt", action="write", content="bar\n"),
                    FileEdit(path="foo.txt", action="delete"),
                ],
            )
            self.assertFalse(target.exists())
            self.assertEqual((root / "bar.txt").read_text(encoding="utf-8"), "bar\n")


if __name__ == "__main__":
    unittest.main()
