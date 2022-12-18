#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import logging
import re
from typing import Iterator, Dict, Union

import requests
from bs4 import BeautifulSoup

from zvg_portal.model import Land, ObjektEntry, RawList, RawEntry
from zvg_portal.parser import VerkehrswertParser, VersteigerungsTerminParser, AddressParser
from zvg_portal.utils import CustomHTTPAdapter


class Endpoints:
    def __init__(self, base_url: str):
        assert base_url[-1] != '/'
        self.index = f'{base_url}/index.php'
        self.form = f'{base_url}/index.php?button=Termine%20suchen'
        self.show_details = f'{base_url}/index.php?button=showZvg'


class ZvgPortal:
    def __init__(self, logger: logging.Logger, user_agent: str, base_url: str):
        self._logger = logger
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
        self._address_parser = AddressParser()
        self._verkehrswert_parser = VerkehrswertParser()
        self._versteigerungs_termin_parser = VersteigerungsTerminParser()

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

    def _parse_html_table(self, soup: BeautifulSoup) -> Iterator[Dict[str, str]]:
        current_row = {}
        for tr in soup.findAll('tr'):
            tds = tr.findAll('td')
            if len(tds) < 2:
                continue

            title = tds[0].text.strip().strip(':')
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

    def _parse_details(self, entry: ObjektEntry, content: bytes) -> ObjektEntry:
        soup = BeautifulSoup(content.decode('latin1'), 'html.parser')
        # TODO parse out external and internal links
        table = next(self._parse_html_table(soup))
        if 'Grundbuch' in table:
            entry.grundbuch = table['Grundbuch'][0]
            del table['Grundbuch']
        if 'Art der Versteigerung' in table:
            entry.art_der_versteigerung = table['Art der Versteigerung'][0]
            del table['Art der Versteigerung']
        if 'Ort der Versteigerung' in table:
            entry.ort_der_versteigerung = table['Ort der Versteigerung'][0]
            del table['Ort der Versteigerung']
        if 'Informationen zum Gläubiger' in table:
            entry.informationen_zum_glaeubiger = table['Informationen zum Gläubiger'][0]
            del table['Informationen zum Gläubiger']
        if 'Beschreibung' in table:
            entry.beschreibung = table['Beschreibung'][0]
            del table['Beschreibung']
        skip_fields = [
            'zvg_id',
            'Objekt/Lage',
            'Verkehrswert in €',
            'Termin',
            'Gericht',
            'GeoServer',
            'GoogleMaps',
            'Gutachten',
            'amtliche Bekanntmachung',
            'Exposee',
            'Änderung',
            'Foto',
            'Hinweis',
        ]
        for title, cells in table.items():
            if title in skip_fields:
                continue
            if self._title_probably_aktenzeichen(title, entry):
                continue
            self._logger.warning(f'Unparsed title "{title}" with cells ({entry.aktenzeichen}): {cells}')

        return entry

    def _title_probably_aktenzeichen(self, title: str, entry: ObjektEntry) -> bool:
        cleaned_title = self._nbsps_to_spaces(title)
        if cleaned_title.split('/')[0] == entry.aktenzeichen.split('/')[0]:
            return True
        if entry.aktenzeichen in cleaned_title.replace('/ ', '/'):
            return True

        return False

    @staticmethod
    def _nbsps_to_spaces(s: str) -> str:
        needle = b'\xc2\xa0'
        while needle in s.encode('utf-8'):
            s = s.encode('utf-8').replace(needle, b' ').decode('utf-8')

        return s

    @staticmethod
    def _remove_duplicate_spaces(s: str) -> str:
        while '  ' in s:
            s = s.replace('  ', ' ')
        return s

    def list(self, land: Land, plz: str = '') -> Iterator[Union[RawList, RawEntry, ObjektEntry]]:
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
        last_raw_list = RawList(content=response.content)
        yield last_raw_list

        soup = BeautifulSoup(response.content.decode('latin1'), 'html.parser')
        table_rows = list(self._parse_html_table(soup))
        for rows in table_rows:
            entry = ObjektEntry(land_short=land.short, raw_list_sha256=last_raw_list.sha256)
            if 'zvg_id' in rows.keys():
                entry.zvg_id = rows['zvg_id']

            for td_content in rows.get('Aktenzeichen', []):
                for aktenzeichen_regex in [self._aktenzeichen_regex_1, self._aktenzeichen_regex_2]:
                    match = aktenzeichen_regex.search(td_content)
                    if match is not None:
                        entry.aktenzeichen = match.group(0)
                        break
            if 'Amtsgericht' in rows.keys():
                entry.amtsgericht = ' '.join(rows['Amtsgericht'])
            if 'Objekt/Lage' in rows.keys():
                entry.objekt_lage = self._remove_duplicate_spaces(' '.join(rows['Objekt/Lage']))
                entry.adresse = self._address_parser.parse(entry.objekt_lage)
                if entry.adresse is None:
                    self._logger.warning(f'Could not parse address out of: {entry.objekt_lage}')
            if 'Verkehrswert in €' in rows.keys():
                entry.verkehrswert_in_cent = self._verkehrswert_parser.cents(rows['Verkehrswert in €'][0])
            if 'Termin' in rows.keys():
                entry.termin_as_str = ' '.join(rows['Termin'])
                if 'wurde aufgehoben' in entry.termin_as_str:
                    entry.wurde_aufgehoben = True
                else:
                    entry.termin_as_date = self._versteigerungs_termin_parser.to_datetime(entry.termin_as_str)

            for key, tds in rows.items():
                for td_content in tds if isinstance(tds, list) else []:
                    match = self._aktualisierung_regex.search(td_content)
                    if match:
                        entry.letzte_aktualisierung = datetime.datetime(
                            year=int(match.group('year'), 10),
                            month=int(match.group('month'), 10),
                            day=int(match.group('day'), 10),
                            hour=int(match.group('hour'), 10),
                            minute=int(match.group('minute'), 10),
                        )
                        continue

            if not entry.any:
                continue

            if entry.zvg_id:
                url = f'{self._base_url}/index.php?button=showZvg&zvg_id={entry.zvg_id}&land_abk={land.short}'
                response = requests.get(url, headers={'Referer': f'{self._base_url}/index.php?button=Suchen'})
                response.raise_for_status()
                last_raw_entry = RawEntry(content=response.content)
                entry.raw_entry_sha256 = last_raw_entry.sha256
                yield last_raw_entry
                if response.content[0:10] == b'\n<!DOCTYPE':
                    entry = self._parse_details(entry, response.content)
                else:
                    self._logger.error(f'Response not valid {entry}, could not : {response.content}')

            yield entry
