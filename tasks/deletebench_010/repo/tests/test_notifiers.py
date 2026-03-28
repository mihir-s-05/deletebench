import unittest

from app.notifiers import available_providers, notify


class NotifierTests(unittest.TestCase):
    def test_slack_exists(self) -> None:
        self.assertIn("slack", available_providers())
        self.assertEqual(notify("slack", "ping"), "slack:ping")
