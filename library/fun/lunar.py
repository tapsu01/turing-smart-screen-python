# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Solar -> Vietnamese lunar calendar conversion, after Ho Ngoc Duc's algorithm
# (https://www.informatik.uni-leipzig.de/~duc/amlich/calrules.html).
# Vietnam uses UTC+7, which occasionally gives a different month start than the Chinese calendar (UTC+8).

import math
from dataclasses import dataclass
from datetime import date

VIETNAM_TIME_ZONE = 7

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]
MONTH_NAMES = ["Giêng", "Hai", "Ba", "Tư", "Năm", "Sáu", "Bảy", "Tám", "Chín", "Mười", "Mười Một", "Chạp"]


@dataclass(frozen=True)
class LunarDate:
    day: int
    month: int
    year: int
    leap: bool

    def day_name(self) -> str:
        return f"Mùng {self.day}" if self.day <= 10 else str(self.day)

    def month_name(self) -> str:
        return MONTH_NAMES[self.month - 1] + (" nhuận" if self.leap else "")

    def year_name(self) -> str:
        return can_chi_year(self.year)


def _jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def _new_moon(k: int) -> float:
    """Julian day of the k-th new moon after 1900-01-01"""
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = math.pi / 180
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 = c1 - 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 = c1 - 0.0004 * math.sin(dr * 3 * mpr)
    c1 = c1 + 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 = c1 - 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 = c1 - 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 = c1 + 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))
    if t < -11:
        delta_t = 0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
    else:
        delta_t = -0.000278 + 0.000265 * t + 0.000262 * t2
    return jd1 + c1 - delta_t


def _sun_longitude(jdn: float) -> float:
    """Sun longitude in radians [0, 2*pi) at the given Julian day"""
    t = (jdn - 2451545.0) / 36525
    t2 = t * t
    dr = math.pi / 180
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(dr * 3 * m)
    longitude = (l0 + dl) * dr
    return longitude - math.pi * 2 * math.floor(longitude / (math.pi * 2))


def _sun_longitude_sector(day_number: int, tz: int) -> int:
    """Sun longitude at local midnight as one of 12 sectors (0 = vernal equinox)"""
    return math.floor(_sun_longitude(day_number - 0.5 - tz / 24) / math.pi * 6)


def _new_moon_day(k: int, tz: int) -> int:
    return math.floor(_new_moon(k) + 0.5 + tz / 24)


def _lunar_month_11(yy: int, tz: int) -> int:
    """Day number of the start of lunar month 11 (the month containing the winter solstice) of year yy"""
    offset = _jd_from_date(31, 12, yy) - 2415021
    k = math.floor(offset / 29.530588853)
    new_moon = _new_moon_day(k, tz)
    if _sun_longitude_sector(new_moon, tz) >= 9:
        new_moon = _new_moon_day(k - 1, tz)
    return new_moon


def _leap_month_offset(a11: int, tz: int) -> int:
    k = math.floor((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    i = 1  # Start with the month following lunar month 11
    arc = _sun_longitude_sector(_new_moon_day(k + i, tz), tz)
    while True:
        last = arc
        i += 1
        arc = _sun_longitude_sector(_new_moon_day(k + i, tz), tz)
        if arc == last or i >= 14:
            break
    return i - 1


def solar_to_lunar(day: date, tz: int = VIETNAM_TIME_ZONE) -> LunarDate:
    day_number = _jd_from_date(day.day, day.month, day.year)
    k = math.floor((day_number - 2415021.076998695) / 29.530588853)
    month_start = _new_moon_day(k + 1, tz)
    if month_start > day_number:
        month_start = _new_moon_day(k, tz)

    a11 = _lunar_month_11(day.year, tz)
    b11 = a11
    if a11 >= month_start:
        lunar_year = day.year
        a11 = _lunar_month_11(day.year - 1, tz)
    else:
        lunar_year = day.year + 1
        b11 = _lunar_month_11(day.year + 1, tz)

    lunar_day = day_number - month_start + 1
    diff = math.floor((month_start - a11) / 29)
    lunar_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = _leap_month_offset(a11, tz)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1

    return LunarDate(lunar_day, lunar_month, lunar_year, lunar_leap)


def can_chi_year(lunar_year: int) -> str:
    return f"{CAN[(lunar_year + 6) % 10]} {CHI[(lunar_year + 8) % 12]}"
