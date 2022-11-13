#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import re
from typing import Iterator, Dict

import requests
from bs4 import BeautifulSoup

from zvg_portal.model import Land, ObjektEntry
from zvg_portal.parser import VerkehrswertParser, VersteigerungsTerminParser
from zvg_portal.utils import CustomHTTPAdapter


class Endpoints:
    def __init__(self, base_url: str):
        assert base_url[-1] != '/'
        self.index = f'{base_url}/index.php'
        self.form = f'{base_url}/index.php?button=Termine%20suchen'
        self.show_details = f'{base_url}/index.php?button=showZvg'


class ZvgPortal:
    def __init__(self, user_agent: str, base_url: str):
        self._session = requests.session()
        self._session.mount('https://', CustomHTTPAdapter())
        self._session.mount('http://', CustomHTTPAdapter())
        self._session.headers = {'User-Agent': user_agent}
        self._base_url = base_url
        self.endpoints = Endpoints(base_url)
        self._zvg_id_regex = re.compile(r'zvg_id=(?P<zvg_id>\d{1,20})')
        self._aktenzeichen_regex_1 = re.compile(r'\d{4} K \d{4}/\d{4}')
        self._aktenzeichen_regex_2 = re.compile(r'K \d{4}/\d{4}')
        self._aktualisierung_regex = re.compile(
            r'letzte Aktualisierung (?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{4}) (?P<hour>\d{2}):(?P<minute>\d{2})'
        )
        self._strip_tags_regex = re.compile('<[^<]+?>')

    def get_laender(self) -> Iterator[Land]:
        response = self._session.get(self.endpoints.form)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for select in soup.findAll('select'):
            correct_select = False
            for option in select.select('option'):
                if correct_select:
                    yield Land(short=option['value'], name=option.text)
                    continue
                if 'Bundesland auswählen' in option.text:
                    correct_select = True
            if correct_select:
                break

    def _clean_value(self, s):
        return self._strip_tags_regex.sub('', s).strip('\n')

    def _parse_list(self, content: bytes) -> Iterator[Dict[str, str]]:
        soup = BeautifulSoup(content, 'html.parser')
        current_row = {}
        for tr in soup.findAll('tr'):
            tds = tr.findAll('td')
            if len(tds) < 2:
                continue

            title = tds[0].text.strip()
            if title == 'Aktenzeichen' and current_row:
                yield current_row
                current_row = {}
            for td in tds:
                a = td.find('a')
                if a is None:
                    continue
                try:
                    match = self._zvg_id_regex.search(a['href'])
                except KeyError:
                    continue
                if match:
                    current_row['zvg_id'] = int(match.group('zvg_id'), 10)

            current_row[title] = [td.text.strip() for td in tds[1:]]

        if current_row:
            yield current_row

    @staticmethod
    def _remove_duplicate_spaces(s: str) -> str:
        while '  ' in s:
            s = s.replace('  ', ' ')
        return s

    def list(self, land: Land, plz: str = '') -> Iterator[ObjektEntry]:
        params = {'button': 'Suchen', 'all': '1'}

        data = {
            'ger_name': '-- Alle Amtsgerichte --',
            'order_by': '2',
            'land_abk': land.short,
            'ger_id': '0',
            'az1': '',
            'az2': '',
            'az3': '',
            'az4': '',
            'art': '',
            'obj': '',
            'str': '',
            'hnr': '',
            'plz': plz,
            'ort': '',
            'ortsteil': '',
            'vtermin': '',
            'btermin': '',
        }

        response = requests.post(self.endpoints.index, params=params, data=data)
        response.raise_for_status()

        table_rows = list(self._parse_list(response.content))
        for rows in table_rows:
            current_object_entry = ObjektEntry(land_short=land.short)
            if 'zvg_id' in rows.keys():
                current_object_entry.zvg_id = rows['zvg_id']

            for td_content in rows.get('Aktenzeichen', []):
                for aktenzeichen_regex in [self._aktenzeichen_regex_1, self._aktenzeichen_regex_2]:
                    match = aktenzeichen_regex.search(td_content)
                    if match is not None:
                        current_object_entry.aktenzeichen = match.group(0)
                        break
            if 'Amtsgericht' in rows.keys():
                current_object_entry.amtsgericht = ' '.join(rows['Amtsgericht'])
            if 'Objekt/Lage' in rows.keys():
                current_object_entry.objekt_lage = self._remove_duplicate_spaces(' '.join(rows['Objekt/Lage']))
            if 'Verkehrswert in €' in rows.keys():
                current_object_entry.verkehrswert_in_cent = VerkehrswertParser().cents(rows['Verkehrswert in €'][0])

            if 'Termin' in rows.keys():
                current_object_entry.termin_as_str = ' '.join(rows['Termin'])
                if 'wurde aufgehoben' in current_object_entry.termin_as_str:
                    current_object_entry.wurde_aufgehoben = True
                else:
                    current_object_entry.termin_as_date = VersteigerungsTerminParser().to_datetime(
                        current_object_entry.termin_as_str
                    )

            for key, tds in rows.items():
                for td_content in tds if isinstance(tds, list) else []:
                    match = self._aktualisierung_regex.search(td_content)
                    if match:
                        current_object_entry.letzte_aktualisierung = datetime.datetime(
                            year=int(match.group('year'), 10),
                            month=int(match.group('month'), 10),
                            day=int(match.group('day'), 10),
                            hour=int(match.group('hour'), 10),
                            minute=int(match.group('minute'), 10),
                        )
                        continue

            if current_object_entry.any:
                yield current_object_entry
