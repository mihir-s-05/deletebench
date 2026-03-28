import unittest

from app.parser import parse


class ParserTests(unittest.TestCase):
    def test_legacy_path_exists(self) -> None:
        self.assertEqual(parse("42"), {"id": "42"})
