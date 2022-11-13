#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import locale
import re
from typing import Optional


class VerkehrswertParser:
    def __init__(self):
        self._r = re.compile(r'[\d,.]{4,20}')

    def cents(self, s: str) -> Optional[int]:
        match = self._r.search(s)
        if not match:
            return
        betrag_str = match.group(0)
        if betrag_str[-3] in [',', '.']:
            cents = int(betrag_str[-2:], 10)
            betrag_without_cents = betrag_str[:-3]
        else:
            cents = 0
            betrag_without_cents = betrag_str
        euro_str = betrag_without_cents.replace('.', '').replace(',', '')
        return int(euro_str, 10) * 100 + cents


class VersteigerungsTerminParser:
    def __init__(self):
        locale.setlocale(locale.LC_ALL, 'de_DE')

    def to_datetime(self, s: str) -> Optional[datetime.datetime]:
        return datetime.datetime.strptime(s, '%A, %d. %B %Y, %H:%M Uhr')
