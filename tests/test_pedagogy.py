import unittest
from datetime import time

from pedagogy import intervals_overlap, parse_time


class TimetableValidationTests(unittest.TestCase):
    def test_parse_time_rejects_invalid_values(self):
        self.assertEqual(parse_time("08:30"), time(8, 30))
        self.assertIsNone(parse_time("25:70"))
        self.assertIsNone(parse_time(""))

    def test_overlapping_intervals(self):
        self.assertTrue(intervals_overlap(time(8, 0), time(9, 0), time(8, 30), time(9, 30)))
        self.assertFalse(intervals_overlap(time(8, 0), time(9, 0), time(9, 0), time(10, 0)))
        self.assertFalse(intervals_overlap(time(10, 0), time(11, 0), time(8, 0), time(9, 0)))


if __name__ == "__main__":
    unittest.main()
