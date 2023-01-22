#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import unittest

from zvg_portal.parser import VersteigerungsTerminParser


class VersteigerungsTerminParserTest(unittest.TestCase):
    def test_default(self):
        dt = VersteigerungsTerminParser().to_datetime('Montag, 23. Januar 2023, 09:30 Uhr')
        self.assertEqual(datetime.datetime(year=2023, month=1, day=23, hour=9, minute=30), dt)

    def test_negativeDay(self):
        dt = VersteigerungsTerminParser().to_datetime('Montag, 30. November -1, 00:00 Uhr')


if __name__ == "__main__":
    unittest.main()
