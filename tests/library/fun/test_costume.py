import unittest
from datetime import date

from library.fun.costume import Costume, costume_for, parse_birthday


class TestCostume(unittest.TestCase):
    def test_tet_from_kitchen_gods_day_to_the_seventh(self):
        self.assertEqual(costume_for(date(2025, 1, 21)), Costume.NONE)
        self.assertEqual(costume_for(date(2025, 1, 22)), Costume.TET)  # 23rd day of the 12th lunar month
        self.assertEqual(costume_for(date(2025, 1, 29)), Costume.TET)  # first day of the lunar year
        self.assertEqual(costume_for(date(2025, 2, 4)), Costume.TET)
        self.assertEqual(costume_for(date(2025, 2, 5)), Costume.NONE)

    def test_mid_autumn(self):
        self.assertEqual(costume_for(date(2025, 10, 6)), Costume.MID_AUTUMN)  # 15th day of the 8th lunar month
        self.assertEqual(costume_for(date(2025, 10, 9)), Costume.NONE)

    def test_christmas_and_new_year(self):
        self.assertEqual(costume_for(date(2025, 12, 25)), Costume.CHRISTMAS)
        self.assertEqual(costume_for(date(2025, 12, 31)), Costume.NEW_YEAR)
        self.assertEqual(costume_for(date(2026, 1, 1)), Costume.NEW_YEAR)
        self.assertEqual(costume_for(date(2025, 12, 28)), Costume.NONE)

    def test_birthday_wins(self):
        self.assertEqual(costume_for(date(2025, 1, 29), (29, 1)), Costume.BIRTHDAY)
        self.assertEqual(costume_for(date(2025, 6, 3), (3, 6)), Costume.BIRTHDAY)
        self.assertEqual(costume_for(date(2025, 6, 4), (3, 6)), Costume.NONE)

    def test_parse_birthday(self):
        self.assertEqual(parse_birthday("03/06"), (3, 6))
        self.assertEqual(parse_birthday("29/2"), (29, 2))
        self.assertIsNone(parse_birthday(""))
        self.assertIsNone(parse_birthday("31/02"))
        self.assertIsNone(parse_birthday("abc"))


if __name__ == '__main__':
    unittest.main()
