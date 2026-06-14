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
        self.assertEqual(adresse.plz, "00000")
        self.assertIsNone(adresse.ort)
        self.assertIsNone(adresse.stadtteil)

    def test_two_street_names_plz_00000(self):
        adresse = AddressParser().parse("Grünfläche, landwirtschaftliche Fläche: Alte Schläfe, Zäunchen, 00000")
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Alte Schläfe, Zäunchen")
        self.assertEqual(adresse.plz, "00000")

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
        self.assertEqual(adresse.plz, "00000")

    def test_house_number_with_suffix_plz_00000(self):
        adresse = AddressParser().parse(
            "Zweifamilienhaus, Zweifamilienhaus mit Garage: Frohnhauser Straße 9, 9a, 00000"
        )
        self.assertIsNotNone(adresse)
        self.assertEqual(adresse.strasse, "Frohnhauser Straße 9, 9a")
        self.assertEqual(adresse.plz, "00000")

    def test_placeholder_dot_strasse_is_rejected(self):
        # The portal sometimes uses '.' as a placeholder when the street is
        # unknown. The strasse char class accepts '.', so without the
        # letter-presence guard this would have been captured as strasse='.'.
        adresse = AddressParser().parse("Eigentumswohnung: ., 80331 München, Altstadt")
        self.assertIsNone(adresse)

    def test_placeholder_dashes_strasse_is_rejected(self):
        adresse = AddressParser().parse("Sonstiges: --, 80331 München")
        self.assertIsNone(adresse)


if __name__ == "__main__":
    unittest.main()
