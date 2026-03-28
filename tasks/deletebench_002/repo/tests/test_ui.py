import unittest

from app.ui import has_modal, nav_items


class UITests(unittest.TestCase):
    def test_feature_is_visible(self) -> None:
        self.assertIn("Changelog", nav_items())
        self.assertTrue(has_modal("changelog"))

    def test_settings_survives(self) -> None:
        self.assertIn("Settings", nav_items())
        self.assertTrue(has_modal("settings"))
