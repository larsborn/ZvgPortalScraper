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
