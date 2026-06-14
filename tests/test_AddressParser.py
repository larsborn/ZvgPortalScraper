#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.parser import AddressParser


class AdressParserTest(unittest.TestCase):
    def test_variant1(self):
        adresse = AddressParser().parse("Eigentumswohnung: Ehinger Str. 75, 47249 Duisburg, Wanheim-Angerhausen")
        self.assertEqual(adresse.strasse, "Ehinger Str. 75")
        self.assertEqual(adresse.plz, "47249")
        self.assertEqual(adresse.ort, "Duisburg")
        self.assertEqual(adresse.stadtteil, "Wanheim-Angerhausen")

    def test_variant2(self):
        adresse = AddressParser().parse(
            "Kfz-Stellplatz (Tiefgarage), Eigentumswohnung (1 bis 2 Zimmer): Beethovenweg 14, 58313 Herdecke"
        )
        self.assertEqual(adresse.strasse, "Beethovenweg 14")
        self.assertEqual(adresse.plz, "58313")
        self.assertEqual(adresse.ort, "Herdecke")
        self.assertEqual(adresse.stadtteil, None)

    def test_variant3(self):
        adresse = AddressParser().parse(
            "land- und forstwirtschaftlich genutztes Grundstück, mit Buchen, Waldfläche, junger Mischbestand, teilweise Aufforstung: "
            'Verlängerung von "In der Lahmich", 51597 Morsbach, Holpe'
        )
        self.assertEqual(adresse.strasse, 'Verlängerung von "In der Lahmich"')
        self.assertEqual(adresse.plz, "51597")
        self.assertEqual(adresse.ort, "Morsbach")
        self.assertEqual(adresse.stadtteil, "Holpe")

    def test_variant4(self):
        adresse = AddressParser().parse("Reihenhaus: Wiesenstraße 1, 52531 Übach-Palenberg")
        self.assertEqual(adresse.strasse, "Wiesenstraße 1")
        self.assertEqual(adresse.plz, "52531")
        self.assertEqual(adresse.ort, "Übach-Palenberg")
        self.assertEqual(adresse.stadtteil, None)

    def test_variant5(self):
        adresse = AddressParser().parse(
            "Baugrundstück: Löhrerlen (früher Löhrerlen 33, 33a), 42279 Wuppertal, Langerfeld"
        )
        self.assertEqual(adresse.strasse, "Löhrerlen (früher Löhrerlen 33, 33a)")
        self.assertEqual(adresse.plz, "42279")
        self.assertEqual(adresse.ort, "Wuppertal")
        self.assertEqual(adresse.stadtteil, "Langerfeld")

    def test_variant6(self):
        adresse = AddressParser().parse(
            "Kfz-Stellplatz (Tiefgarage): "
            "EKZ Röttgen (Hans-Böckler-Str. 147-153, Röttgen 141-175), 42109 Wuppertal, Elberfeld"
        )
        self.assertEqual(adresse.strasse, "EKZ Röttgen (Hans-Böckler-Str. 147-153, Röttgen 141-175)")
        self.assertEqual(adresse.plz, "42109")
        self.assertEqual(adresse.ort, "Wuppertal")
        self.assertEqual(adresse.stadtteil, "Elberfeld")

    def test_multiple_house_numbers_with_stadtteil(self):
        # Real sample from Hessen (observed via scraper warning).
        adresse = AddressParser().parse(
            "Sonstiges, Kfz-Stellplatz (Tiefgarage): " "Troyesstraße 48, 50, 52, 54, 56    , 64297 Darmstadt, Eberstadt"
        )
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Troyesstraße 48, 50, 52, 54, 56")
        self.assertEqual(adresse.plz, "64297")
        self.assertEqual(adresse.ort, "Darmstadt")
        self.assertEqual(adresse.stadtteil, "Eberstadt")

    def test_multiple_house_numbers_plz_00000(self):
        adresse = AddressParser().parse("Eigentumswohnung (1 bis 2 Zimmer): Papenberger Straße 26, 28, 30, 00000")
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Papenberger Straße 26, 28, 30")
        # '00000' is a sentinel for "no PLZ" -> stored as None.
        self.assertIsNone(adresse.plz)
        self.assertIsNone(adresse.ort)
        self.assertIsNone(adresse.stadtteil)

    def test_two_street_names_plz_00000(self):
        adresse = AddressParser().parse("Grünfläche, landwirtschaftliche Fläche: Alte Schläfe, Zäunchen, 00000")
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Alte Schläfe, Zäunchen")
        self.assertIsNone(adresse.plz)

    def test_many_house_numbers_two_streets_plz_00000(self):
        adresse = AddressParser().parse(
            "unbebautes Grünland bzw. Privatweg genutzte Grundstück: "
            "Willers Kamp 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, An der Eisenbahn, 00000"
        )
        self.assertIsNotNone(adresse)
        self.assertEqual(
            adresse.strasse,
            "Willers Kamp 48, 50, 52, 54, 56, 58, 60, 62, 64, 66, 68, An der Eisenbahn",
        )
        self.assertIsNone(adresse.plz)

    def test_house_number_with_suffix_plz_00000(self):
        adresse = AddressParser().parse(
            "Zweifamilienhaus, Zweifamilienhaus mit Garage: Frohnhauser Straße 9, 9a, 00000"
        )
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Frohnhauser Straße 9, 9a")
        self.assertIsNone(adresse.plz)

    def test_placeholder_dot_strasse_drops_strasse_keeps_location(self):
        # The portal uses '.' as a placeholder when the street is unknown.
        # We don't want to capture '.' as the street, but we do want to keep
        # the PLZ/Ort/Stadtteil that were present alongside it.
        adresse = AddressParser().parse("Eigentumswohnung: ., 80331 München, Altstadt")
        self.assertIsNotNone(adresse)
        self.assertIsNone(adresse.strasse)
        self.assertEqual(adresse.plz, "80331")
        self.assertEqual(adresse.ort, "München")
        self.assertEqual(adresse.stadtteil, "Altstadt")

    def test_placeholder_dash_strasse_drops_strasse_keeps_location(self):
        # Real Brandenburg sample from production logs.
        adresse = AddressParser().parse("unbebautes Grundstück, Ackerland: -, 03226 Vetschau")
        self.assertIsNotNone(adresse)
        self.assertIsNone(adresse.strasse)
        self.assertEqual(adresse.plz, "03226")
        self.assertEqual(adresse.ort, "Vetschau")
        self.assertIsNone(adresse.stadtteil)

    def test_placeholder_dot_strasse_with_compound_ort_and_stadtteil(self):
        # Real Brandenburg sample from production logs.
        adresse = AddressParser().parse(
            "land- und forstwirtschaftlich genutztes Grundstück: ., 16306 Groß Pinnow, Hohenselchow"
        )
        self.assertIsNotNone(adresse)
        self.assertIsNone(adresse.strasse)
        self.assertEqual(adresse.plz, "16306")
        self.assertEqual(adresse.ort, "Groß Pinnow")
        self.assertEqual(adresse.stadtteil, "Hohenselchow")

    def test_truly_unparseable_input_still_returns_none(self):
        # No PLZ at all -> no pattern matches, nothing to fall back to.
        adresse = AddressParser().parse("Eigentumswohnung mit Garten, irgendwo in Berlin")
        self.assertIsNone(adresse)

    def test_semicolon_separated_streets_with_plus_house_number(self):
        # Real Frankfurt sample: two streets joined by ';' and a '+' between
        # house numbers. Pattern 1 would have captured strasse='7' (the '7'
        # after the '+', before the PLZ) without the letter-presence guard.
        adresse = AddressParser().parse(
            "Eigentumswohnung (3 bis 4 Zimmer): "
            "Graf-von-Stauffenberg-Allee 79, 81, 83;Hans-Poelzig-Str. 5+7, "
            "60438 Frankfurt am Main, Kalbach"
        )
        self.assertIsNotNone(adresse)
        self.assertEqual(
            adresse.strasse,
            "Graf-von-Stauffenberg-Allee 79, 81, 83;Hans-Poelzig-Str. 5+7",
        )
        self.assertEqual(adresse.plz, "60438")
        self.assertEqual(adresse.ort, "Frankfurt am Main")
        self.assertEqual(adresse.stadtteil, "Kalbach")


if __name__ == "__main__":
    unittest.main()
