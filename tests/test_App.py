#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import locale
import unittest
from unittest import mock

from zvg_portal.app import format_currency_eur


class AppTest(unittest.TestCase):
    def test_format_currency_falls_back_without_locale_currency(self):
        with mock.patch.object(locale, 'currency', side_effect=ValueError):
            self.assertEqual('1.234,56 €', format_currency_eur(123456))


if __name__ == '__main__':
    unittest.main()
