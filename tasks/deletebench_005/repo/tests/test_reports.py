import unittest

from app.api import available_routes
from app.reports import export_csv, export_formats, export_json


class ReportTests(unittest.TestCase):
    def test_csv_export_exists(self) -> None:
        rows = [{"name": "ana", "score": "9"}]
        self.assertIn("csv", export_formats())
        self.assertEqual(export_csv(rows), "name,score\nana,9")
        self.assertIn("/reports/export/csv", available_routes())

    def test_json_export_survives(self) -> None:
        rows = [{"name": "ana", "score": "9"}]
        self.assertIn("json", export_formats())
        self.assertEqual(export_json(rows), rows)
