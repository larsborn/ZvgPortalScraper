#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.runner import parse_interval


class TestParseInterval(unittest.TestCase):
    def test_valid_specs(self):
        cases = [
            ("90s", 90),
            ("30m", 30 * 60),
            ("6h", 6 * 3600),
            ("1h30m", 1 * 3600 + 30 * 60),
            ("2h15m45s", 2 * 3600 + 15 * 60 + 45),
            ("21600", 21600),  # plain int → seconds
            ("0s", 0),
        ]
        for spec, expected_seconds in cases:
            with self.subTest(spec=spec):
                self.assertEqual(parse_interval(spec), expected_seconds)

    def test_invalid_specs_raise_value_error(self):
        bad_cases = [
            "",
            "6x",  # unknown unit
            "-1h",  # negative not allowed
            "1.5h",  # no decimals
            "h30m",  # leading unit without number
            "6 h",  # whitespace
            "6H",  # uppercase units not allowed
            "abc",
            "30m6",  # trailing number without unit
        ]
        for bad in bad_cases:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_interval(bad)

    def test_none_raises(self):
        with self.assertRaises(ValueError):
            parse_interval(None)


if __name__ == "__main__":
    unittest.main()
