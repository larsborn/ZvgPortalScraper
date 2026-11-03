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

    # --- more than two decimals is either a fused value or not money ------

    def test_hektar_from_a_nested_parcel_table(self):
        """by/48783. The Verkehrswert cell contains a nested parcel table, and
        BeautifulSoup's find_all("td") is recursive, so its cells flatten into
        the same row. Both the old parser and the first rewrite picked the
        Hektar figure 0,0876 out of it — EUR 876 and EUR 0.08 respectively for
        a plot the page values at 150.000,00 EUR further down."""
        cell = (
            "Gemarkung Flurstueck Wirtschaftsart u. Lage Anschrift Hektar "
            "Senden 662/16 Bauplatz An der Harderstrasse 0,0876 "
            "Objektbeschreibung Verkehrswert: 150.000,00 €"
        )
        self.assertEqual(VerkehrswertParser().cents(cell), 150_000 * 100)

    def test_bare_four_decimal_number_is_not_money(self):
        self.assertIsNone(VerkehrswertParser().cents("0,6355"))
        self.assertIsNone(VerkehrswertParser().cents("0,0876"))

    def test_grouped_thousands_still_truncate(self):
        """A fused or mistyped value keeps its euros, because the thousands
        grouping shows where they end."""
        self.assertEqual(VerkehrswertParser().cents("285.000,002"), 285_000 * 100)
        self.assertEqual(VerkehrswertParser().cents("102.000,000"), 102_000 * 100)

    # --- a nested table labels its own value ------------------------------

    def test_nested_table_label_beats_surrounding_prose(self):
        """rp/3786. The cell holds an Objektbeschreibung and a nested table.
        BeautifulSoup concatenates text across elements without a separator,
        so scanning the whole cell produced "6,50" — a string that does not
        appear anywhere in the page."""
        cell = (
            "Lfd. Nr. 1 Objektbeschreibung/Lage (lt Angabe d. Sachverstaendigen): "
            "Miteigentumsanteil nebst Sondereigentum an"
            "Verkehrswert:187.000,00 €Verkehrswert:14.300,00 €"
        )
        self.assertEqual(VerkehrswertParser().cents(cell), 187_000 * 100)

    def test_nested_table_label_beats_a_hektar_column(self):
        cell = (
            "Gemarkung Flurstueck Anschrift Hektar Senden 662/16 Bauplatz 0,0876 "
            "Objektbeschreibung Verkehrswert: 150.000,00 €"
        )
        self.assertEqual(VerkehrswertParser().cents(cell), 150_000 * 100)

    def test_gesamtverkehrswert_is_not_a_nested_label(self):
        """The label needs its colon; "Gesamtverkehrswert = 40.000,00" must
        still be read as a plain cell."""
        self.assertEqual(VerkehrswertParser().cents("Gesamtverkehrswert = 40.000,00 €"), 40_000 * 100)

    def test_gesamtverkehrswert_label_is_not_followed(self):
        """A "Gesamtverkehrswert:" is a sum, not this cell's own label.
        Following it flipped 89 multi-object listings from the first stated
        value to the total — arguably better data, but a decision about what
        an auction is worth rather than about parsing, and it would only apply
        where the portal happens to print a total."""
        self.assertEqual(
            VerkehrswertParser().cents(
                "Blatt 1434: 54.400,00 € Blatt 1435: 58.800,00 € " "Gesamtverkehrswert: 113.200,00 €"
            ),
            54_400 * 100,
        )
        self.assertEqual(
            VerkehrswertParser().cents(
                "Verkehrswerte: 5.980,00 € (lfd. Nr. 1), 880,00 € (lfd. Nr. 2) " "Gesamtverkehrswert: 344.000,00"
            ),
            5_980 * 100,
        )

    def test_area_unit_means_it_is_not_a_price(self):
        """rp/3886 was stored as EUR 178.26 — its Wohnflaeche."""
        self.assertEqual(
            VerkehrswertParser().cents(
                "Lfd. Nr. 1 Einfamilienhaus: Wohnflaeche: ca. 178,26 m², mit Garage "
                "Verkehrswert: 194.000,00 € davon entfaellt auf Zubehoer: 17.000,00 €"
            ),
            194_000 * 100,
        )

    def test_hyphenated_gesamt_label_is_also_a_sum(self):
        """ "Gesamt-Verkehrswert:" with a hyphen slipped past a lookbehind
        written only for "Gesamtverkehrswert:"."""
        self.assertEqual(
            VerkehrswertParser().cents(
                "Lfd. Nr. 1: 1/2-Anteil an Fl.St. 58/3: 50.500,00 Euro "
                "Lfd. Nr. 2: 1/2-Anteil an Fl.St. 58/3: 50.500,00 Euro "
                "Gesamt-Verkehrswert: 101.000,00 Euro"
            ),
            50_500 * 100,
        )
        self.assertEqual(
            VerkehrswertParser().cents(
                "1/2 Anteil lfd. Nr. 1: 142.500,00 EUR 1/2 Anteil lfd. Nr. 2: 142.500,00 EUR "
                "Gesamt-Verkehrswert: 285.000,00 EUR"
            ),
            142_500 * 100,
        )


if __name__ == "__main__":
    unittest.main()
