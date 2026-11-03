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

    # --- ordinals must not be mistaken for amounts ------------------------
    # Found by re-parsing all 8,016 current listings with the new parser and
    # diffing against the database. Dropping the old {4,20} length bound let a
    # bare "1" win, so these parsed as EUR 1.

    def test_objekt_ordinal_is_not_the_amount(self):
        self.assertEqual(VerkehrswertParser().cents("Objekt 1: 14.000,00 Objekt 2: 55.500,00"), 14_000 * 100)

    def test_lfd_nr_ordinal_with_trailing_dot(self):
        """The token here is "1." — not str.isdigit(), so a guard written
        against the raw token misses it."""
        self.assertEqual(VerkehrswertParser().cents("Lfd.Nr. 1.: 375.000,00 Lfd.Nr. 2.: 4.000,00"), 375_000 * 100)

    def test_bv_nr_ordinal_is_not_the_amount(self):
        self.assertEqual(VerkehrswertParser().cents("BV-Nr. 1: 204.000,00 BV-Nr. 2: 35.000,00"), 204_000 * 100)

    def test_short_number_still_wins_when_the_currency_follows_it(self):
        """450 is only three digits, but "EUR" right after it settles the
        question; the Flurstueck number before it does not have that."""
        self.assertEqual(
            VerkehrswertParser().cents("Flurstueck 178: 450,-- EUR Flurstueck 179: 125.000,-- EUR"),
            450 * 100,
        )

    def test_double_dash_means_no_cents(self):
        self.assertEqual(VerkehrswertParser().cents("125.000,-- EUR"), 125_000 * 100)

    def test_label_without_a_value(self):
        self.assertIsNone(VerkehrswertParser().cents("Verkehrswert:"))
        self.assertIsNone(VerkehrswertParser().cents("Lfd. Nr. 1 Verkehrswert:"))

    # --- the first stated amount wins, not the one nearest a currency -----
    # "currency-adjacent wins outright" looked right on the Blatt cases and
    # was wrong on every cell that glosses a breakdown after the total.

    def test_total_before_breakdown(self):
        self.assertEqual(
            VerkehrswertParser().cents("Gesamt: 11.250,00 Einzelwerte: lfd. Nr. 9: 1.615,00€, lfd. Nr. 10:"),
            11_250 * 100,
        )

    def test_value_before_share_note(self):
        self.assertEqual(
            VerkehrswertParser().cents("160.000,00 - je 1/2 Miteigentumsanteil 80.000,00 Euro -"),
            160_000 * 100,
        )

    def test_value_before_zubehoer_note(self):
        self.assertEqual(
            VerkehrswertParser().cents("501.000,-- davon entfällt auf Zubehör: 8.000,-- € (Einbauküche)"),
            501_000 * 100,
        )

    def test_ordinal_before_the_value(self):
        self.assertEqual(VerkehrswertParser().cents("Lfd. Nr. 1 202.000,00 Lfd. Nr. 2 647.705,00"), 202_000 * 100)

    def test_trailing_full_stop(self):
        """ "119.000,00." was read as 11,900,000 because the old cents test
        looked at a fixed offset from the end."""
        self.assertEqual(VerkehrswertParser().cents("119.000,00."), 119_000 * 100)
        self.assertEqual(VerkehrswertParser().cents("1,00."), 100)

    def test_bare_number_with_currency(self):
        self.assertEqual(VerkehrswertParser().cents("90 €"), 90 * 100)


if __name__ == "__main__":
    unittest.main()
