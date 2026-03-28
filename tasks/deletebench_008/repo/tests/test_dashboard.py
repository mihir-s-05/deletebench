import unittest

from app.dashboard import dashboard_cards


class DashboardTests(unittest.TestCase):
    def test_flagged_card_exists(self) -> None:
        self.assertIn("Audit Preview", dashboard_cards())
