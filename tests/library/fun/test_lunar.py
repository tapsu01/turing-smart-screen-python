import unittest
from datetime import date

from library.fun.lunar import LunarDate, can_chi_year, solar_to_lunar


class TestLunar(unittest.TestCase):
    def test_tet(self):
        self.assertEqual(solar_to_lunar(date(2024, 2, 10)), LunarDate(1, 1, 2024, False))
        self.assertEqual(solar_to_lunar(date(2025, 1, 29)), LunarDate(1, 1, 2025, False))
        self.assertEqual(solar_to_lunar(date(2026, 2, 17)), LunarDate(1, 1, 2026, False))

    def test_day_before_tet_belongs_to_previous_lunar_year(self):
        lunar = solar_to_lunar(date(2026, 2, 16))
        self.assertEqual((lunar.month, lunar.year), (12, 2025))

    def test_vietnam_time_zone(self):
        # Tet 1985 was on January 21st in Vietnam (UTC+7) but on February 20th in China (UTC+8)
        self.assertEqual(solar_to_lunar(date(1985, 1, 21)), LunarDate(1, 1, 1985, False))
        self.assertEqual(solar_to_lunar(date(1985, 1, 21), tz=8).month, 12)

    def test_leap_months(self):
        self.assertEqual(solar_to_lunar(date(2023, 3, 22)), LunarDate(1, 2, 2023, True))
        self.assertEqual(solar_to_lunar(date(2025, 7, 25)), LunarDate(1, 6, 2025, True))

    def test_names(self):
        self.assertEqual(can_chi_year(2024), "Giáp Thìn")
        self.assertEqual(can_chi_year(2025), "Ất Tỵ")
        self.assertEqual(can_chi_year(2026), "Bính Ngọ")
        lunar = LunarDate(1, 1, 2026, False)
        self.assertEqual((lunar.day_name(), lunar.month_name(), lunar.year_name()), ("Mùng 1", "Giêng", "Bính Ngọ"))
        self.assertEqual(LunarDate(15, 12, 2025, False).day_name(), "15")
        self.assertEqual(LunarDate(1, 6, 2025, True).month_name(), "Sáu nhuận")


if __name__ == '__main__':
    unittest.main()
