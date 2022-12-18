#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.parser import AddressParser


class AdressParserTest(unittest.TestCase):
    def test_variant1(self):
        adresse = AddressParser().parse('Eigentumswohnung: Ehinger Str. 75, 47249 Duisburg, Wanheim-Angerhausen')
        self.assertEqual(adresse.strasse, 'Ehinger Str. 75')
        self.assertEqual(adresse.plz, '47249')
        self.assertEqual(adresse.ort, 'Duisburg')
        self.assertEqual(adresse.stadtteil, 'Wanheim-Angerhausen')

    def test_variant2(self):
        adresse = AddressParser().parse(
            'Kfz-Stellplatz (Tiefgarage), Eigentumswohnung (1 bis 2 Zimmer): Beethovenweg 14, 58313 Herdecke'
        )
        self.assertEqual(adresse.strasse, 'Beethovenweg 14')
        self.assertEqual(adresse.plz, '58313')
        self.assertEqual(adresse.ort, 'Herdecke')
        self.assertEqual(adresse.stadtteil, None)

    def test_variant3(self):
        adresse = AddressParser().parse(
            'land- und forstwirtschaftlich genutztes Grundstück, mit Buchen, Waldfläche, junger Mischbestand, teilweise Aufforstung: '
            'Verlängerung von "In der Lahmich", 51597 Morsbach, Holpe'
        )
        self.assertEqual(adresse.strasse, 'Verlängerung von "In der Lahmich"')
        self.assertEqual(adresse.plz, '51597')
        self.assertEqual(adresse.ort, 'Morsbach')
        self.assertEqual(adresse.stadtteil, 'Holpe')

    def test_variant4(self):
        adresse = AddressParser().parse('Reihenhaus: Wiesenstraße 1, 52531 Übach-Palenberg')
        self.assertEqual(adresse.strasse, 'Wiesenstraße 1')
        self.assertEqual(adresse.plz, '52531')
        self.assertEqual(adresse.ort, 'Übach-Palenberg')
        self.assertEqual(adresse.stadtteil, None)

    def test_variant5(self):
        adresse = AddressParser().parse(
            'Baugrundstück: Löhrerlen (früher Löhrerlen 33, 33a), 42279 Wuppertal, Langerfeld'
        )
        self.assertEqual(adresse.strasse, 'Löhrerlen (früher Löhrerlen 33, 33a)')
        self.assertEqual(adresse.plz, '42279')
        self.assertEqual(adresse.ort, 'Wuppertal')
        self.assertEqual(adresse.stadtteil, 'Langerfeld')

    def test_variant6(self):
        adresse = AddressParser().parse(
            'Kfz-Stellplatz (Tiefgarage): '
            'EKZ Röttgen (Hans-Böckler-Str. 147-153, Röttgen 141-175), 42109 Wuppertal, Elberfeld'
        )
        self.assertEqual(adresse.strasse, 'EKZ Röttgen (Hans-Böckler-Str. 147-153, Röttgen 141-175)')
        self.assertEqual(adresse.plz, '42109')
        self.assertEqual(adresse.ort, 'Wuppertal')
        self.assertEqual(adresse.stadtteil, 'Elberfeld')


if __name__ == "__main__":
    unittest.main()
