import json
import tempfile
import unittest
from pathlib import Path

from deletebench.utils.residue import load_residue_rules


class ResidueRuleTests(unittest.TestCase):
    def test_load_residue_rules_supports_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "rules.json"
            path.write_text(
                json.dumps(
                    {
                        "banned_patterns": ["foo"],
                        "forbidden_symbols": ["bar"],
                        "forbidden_paths": ["baz.txt"],
                    }
                ),
                encoding="utf-8",
            )
            rules = load_residue_rules(path)
            self.assertEqual(rules["banned_patterns"], ["foo"])
            self.assertEqual(rules["forbidden_symbols"], ["bar"])
            self.assertEqual(rules["forbidden_paths"], ["baz.txt"])

    def test_load_residue_rules_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "rules.json"
            path.write_text("{invalid", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_residue_rules(path)


if __name__ == "__main__":
    unittest.main()
