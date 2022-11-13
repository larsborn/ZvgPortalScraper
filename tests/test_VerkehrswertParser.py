#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.parser import VerkehrswertParser


class VerkehrswertParserTest(unittest.TestCase):
    def test_variant1(self):
        self.assertEqual(VerkehrswertParser().cents('3.000.00 EURO'), 3_000 * 100)

    def test_variant2(self):
        self.assertEqual(VerkehrswertParser().cents('3.000,00 EURO'), 3_000 * 100)

    def test_variant3(self):
        self.assertEqual(VerkehrswertParser().cents('4.700,00 €'), 4700 * 100)

    def test_variant4(self):
        self.assertEqual(VerkehrswertParser().cents('256.000 EUR'), 256_000 * 100)

    def test_variant5(self):
        self.assertEqual(VerkehrswertParser().cents('48.600,- €'), 48_600 * 100)

    def test_variant6(self):
        self.assertEqual(VerkehrswertParser().cents('Gesamtverkehrswert = 40.000,00 €'), 40_000 * 100)


if __name__ == "__main__":
    unittest.main()
