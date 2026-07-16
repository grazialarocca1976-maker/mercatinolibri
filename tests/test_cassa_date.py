import unittest

from cassa import format_date_for_db, format_date_for_display


class TestCassaDateFormatting(unittest.TestCase):
    def test_format_date_for_db(self):
        self.assertEqual(format_date_for_db("14/07/2026"), "2026-07-14")
        self.assertEqual(format_date_for_db("2026-07-14"), "2026-07-14")

    def test_format_date_for_display(self):
        self.assertEqual(format_date_for_display("2026-07-14"), "14/07/2026")
        self.assertEqual(format_date_for_display(None), "")


if __name__ == "__main__":
    unittest.main()
