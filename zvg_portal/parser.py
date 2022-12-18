#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import locale
import re
from typing import Optional

from zvg_portal.model import Addresse


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


class AddressParser:
    def __init__(self):
        self._regexes = [
            re.compile(
                r'(?P<strasse>[äüöÄÜÖß (),a-zA-Z0-9-".]+), '
                r'(?P<plz>\d{5}) '
                r'(?P<ort>[äüöÄÜÖß a-zA-Z0-9-.]+), '
                r'(?P<stadtteil>[äüöÄÜÖß a-zA-Z0-9-.]+)'
            ),
            re.compile(r'(?P<strasse>[äüöÄÜÖß (),a-zA-Z0-9-."]+), (?P<plz>\d{5}) (?P<ort>[äüöÄÜÖß a-zA-Z0-9-.]+)'),
        ]

    def parse(self, s: str) -> Optional[Addresse]:
        for r in self._regexes:
            m = r.search(s)
            if m:
                ret = Addresse(
                    strasse=m.group('strasse').strip(),
                    plz=m.group('plz').strip(),
                    ort=m.group('ort').strip(),
                )
                try:
                    ret.stadtteil = m.group('stadtteil').strip()
                except IndexError:
                    pass

                return ret


class VersteigerungsTerminParser:
    def __init__(self):
        locale.setlocale(locale.LC_ALL, 'de_DE')

    def to_datetime(self, s: str) -> Optional[datetime.datetime]:
        return datetime.datetime.strptime(s, '%A, %d. %B %Y, %H:%M Uhr')
