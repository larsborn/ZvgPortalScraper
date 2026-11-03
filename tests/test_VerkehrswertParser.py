#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.parser import VerkehrswertParser


class VerkehrswertParserTest(unittest.TestCase):
    def test_variant1(self):
        self.assertEqual(VerkehrswertParser().cents("3.000.00 EURO"), 3_000 * 100)

    def test_variant2(self):
        self.assertEqual(VerkehrswertParser().cents("3.000,00 EURO"), 3_000 * 100)

    def test_variant3(self):
        self.assertEqual(VerkehrswertParser().cents("4.700,00 €"), 4700 * 100)

    def test_variant4(self):
        self.assertEqual(VerkehrswertParser().cents("256.000 EUR"), 256_000 * 100)

    def test_variant5(self):
        self.assertEqual(VerkehrswertParser().cents("48.600,- €"), 48_600 * 100)

    def test_variant6(self):
        self.assertEqual(VerkehrswertParser().cents("Gesamtverkehrswert = 40.000,00 €"), 40_000 * 100)

    # --- regressions from live data (zvg, 2026-11-03) ---------------------
    # Each string below is the real cell text of a production listing whose
    # stored Verkehrswert was wrong.

    def test_multi_value_fused_by_br_tag(self):
        """by/48861. The portal lists two objects. With one <p> per value the
        caller's rows[...][0] picks the first and all is well; this listing
        put both in ONE <p> separated by <br/>, so "2)" fused onto the
        decimals. ",002" is not two decimals, and the old parser therefore
        read the lot as whole euros: 285,000,002 instead of 285,000."""
        self.assertEqual(VerkehrswertParser().cents("1) 285.000,002) 19.000,00"), 285_000 * 100)

    def test_multi_value_fused_by_br_tag_smaller(self):
        """by/48930, same shape: stored as 10,200,002 instead of 10,200."""
        self.assertEqual(VerkehrswertParser().cents("1) 10.200,002) 16.006,00"), 10_200 * 100)

    def test_three_decimal_places_from_the_portal(self):
        """rp/3876. The portal itself wrote three decimals. Same 1000x
        inflation: stored as 102,000,000 for an Einfamilienhaus."""
        self.assertEqual(VerkehrswertParser().cents("Verkehrswert: 102.000,000 €"), 102_000 * 100)

    def test_prose_before_the_amount(self):
        """ni/13564. The cell leads with a Grundbuch reference, so the first
        numeric run was the Blatt number: stored as 1,787 instead of 30,000."""
        self.assertEqual(
            VerkehrswertParser().cents("Grundbuch von Uelsen Blatt 1787 lfd.Nr. 13 (11): 30.000,00 €"),
            30_000 * 100,
        )

    def test_enumeration_markers_are_not_amounts(self):
        self.assertEqual(VerkehrswertParser().cents("1) 339.500,00"), 339_500 * 100)
        self.assertEqual(VerkehrswertParser().cents("1) 339.500,00 2) 500,00 3) 5.000,00 4) 15.000,00"), 339_500 * 100)

    def test_currency_adjacent_value_wins(self):
        """A number next to the currency beats an earlier bare one."""
        self.assertEqual(VerkehrswertParser().cents("Flurstueck 1234, Wert 50.000,00 EUR"), 50_000 * 100)

    def test_no_amount(self):
        self.assertIsNone(VerkehrswertParser().cents("keine Angabe"))
        self.assertIsNone(VerkehrswertParser().cents(""))


if __name__ == "__main__":
    unittest.main()
