#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterator, Union

import requests
from bs4 import BeautifulSoup, UnicodeDammit

from zvg_portal.model import Land, ObjektEntry, RawAnhang, RawEntry, RawList
from zvg_portal.parser import AddressParser, VerkehrswertParser, VersteigerungsTerminParser
from zvg_portal.utils import CustomHTTPAdapter


class Endpoints:
    def __init__(self, base_url: str):
        assert base_url[-1] != "/"
        self.index = f"{base_url}/index.php"
        self.form = f"{base_url}/index.php?button=Termine%20suchen"
        self.show_details = f"{base_url}/index.php?button=showZvg"


class ZvgPortal:
    def __init__(self, logger: logging.Logger, user_agent: str, base_url: str):
        self._logger = logger
        self._session = requests.session()
        self._session.mount("https://", CustomHTTPAdapter())
        self._session.mount("http://", CustomHTTPAdapter())
        self._session.headers = {"User-Agent": user_agent}
        self._base_url = base_url
        self.endpoints = Endpoints(base_url)
        self._zvg_id_regex = re.compile(r"zvg_id=(?P<zvg_id>\d{1,20})")
        self._aktenzeichen_regex_1 = re.compile(r"\d{4} K \d{4}/\d{4}")
        self._aktenzeichen_regex_2 = re.compile(r"K \d{4}/\d{4}")
        self._aktualisierung_regex = re.compile(
            r"letzte Aktualisierung (?P<day>\d{2})-(?P<month>\d{2})-(?P<year>\d{4}) (?P<hour>\d{2}):(?P<minute>\d{2})"
        )
        self._strip_tags_regex = re.compile("<[^<]+?>")
        self._attachment_link = re.compile(r"\?button=showAnhang&land_abk=[a-z]{2}&file_id=\d+&zvg_id=\d+")
        self._address_parser = AddressParser()
        self._verkehrswert_parser = VerkehrswertParser()
        self._versteigerungs_termin_parser = VersteigerungsTerminParser()
        # Performance/config
        self._timeout = int(os.environ.get("ZVG_TIMEOUT", "30"))
        self._max_workers = int(os.environ.get("ZVG_MAX_WORKERS", "8"))

    def _decode_html(self, content: bytes) -> str:
        """Robustly decode HTML bytes to Unicode (fix common mojibake)."""
        dammit = UnicodeDammit(content, is_html=True)
        if dammit.unicode_markup:
            return dammit.unicode_markup
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return content.decode("latin1", errors="ignore")

    def get_laender(self) -> Iterator[Land]:
        response = self._session.get(self.endpoints.form, timeout=self._timeout)
        response.raise_for_status()
        soup = BeautifulSoup(self._decode_html(response.content), "html.parser")
        for select in soup.find_all("select"):
            correct_select = False
            for option in select.select("option"):
                if correct_select:
                    yield Land(short=option["value"], name=option.text)
                    continue
                if "Bundesland auswählen" in option.text:
                    correct_select = True
            if correct_select:
                break

    def _clean_value(self, s):
        return self._strip_tags_regex.sub("", s).strip("\n")

    def _parse_html_table(self, soup: BeautifulSoup) -> Iterator[Dict[str, str]]:
        current_row = {}
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            title = tds[0].text.strip().strip(":")
            if title == "Aktenzeichen" and current_row:
                yield current_row
                current_row = {}
            for td in tds:
                a = td.find("a")
                if a is None:
                    continue
                try:
                    match = self._zvg_id_regex.search(a["href"])
                except KeyError:
                    continue
                if match:
                    current_row["zvg_id"] = int(match.group("zvg_id"), 10)

            current_row[title] = [td.text.strip() for td in tds[1:]]

        if current_row:
            yield current_row

    def _parse_details(self, entry: ObjektEntry, content: bytes) -> Iterator[Union[ObjektEntry, RawAnhang]]:
        soup = BeautifulSoup(self._decode_html(content), "html.parser")
        skip_startswith = [
            "index.php?button=",
            "?button=",
            "https://justiz.de",
            "http://www.handelsregister.de",
            "javascript:",
            "#",
        ]
        for a in soup.find_all("a"):
            try:
                href = a["href"]
                if self._attachment_link.match(href):
                    response = self._session.get(
                        f"{self._base_url}/{href}",
                        headers={"Referer": f"{self._base_url}/index.php?button=Suchen"},
                        timeout=self._timeout,
                    )
                    response.raise_for_status()
                    raw_anhang = RawAnhang(content=response.content)
                    entry.anhang_sha256s.append(raw_anhang.sha256)
                    yield raw_anhang
                elif any(href.startswith(s) for s in skip_startswith):
                    continue
                else:
                    entry.urls.append(href)
            except KeyError:
                continue

        table = next(self._parse_html_table(soup), None)
        if table is None:
            self._logger.warning(f"Could not find details table for {entry}.")
            yield entry
            return
        if "Grundbuch" in table:
            entry.grundbuch = table["Grundbuch"][0]
            del table["Grundbuch"]
        if "Art der Versteigerung" in table:
            entry.art_der_versteigerung = table["Art der Versteigerung"][0]
            del table["Art der Versteigerung"]
        if "Ort der Versteigerung" in table:
            entry.ort_der_versteigerung = table["Ort der Versteigerung"][0]
            del table["Ort der Versteigerung"]
        if "Informationen zum Gläubiger" in table:
            entry.informationen_zum_glaeubiger = table["Informationen zum Gläubiger"][0]
            del table["Informationen zum Gläubiger"]
        if "Beschreibung" in table:
            entry.beschreibung = table["Beschreibung"][0]
            del table["Beschreibung"]
        skip_fields = [
            "zvg_id",
            "Objekt/Lage",
            "Verkehrswert in €",
            "Termin",
            "Gericht",
            "GeoServer",
            "GoogleMaps",
            "Gutachten",
            "amtliche Bekanntmachung",
            "Exposee",
            "Änderung",
            "Foto",
            "Hinweis",
        ]
        for title, cells in table.items():
            if title in skip_fields:
                continue
            if self._title_probably_aktenzeichen(title, entry):
                continue
            self._logger.debug(f"Unparsed title {repr(title)} with cells ({entry.aktenzeichen}): {cells}")

        yield entry

    def _title_probably_aktenzeichen(self, title: str, entry: ObjektEntry) -> bool:
        cleaned_title = self._nbsps_to_spaces(title)
        if cleaned_title is None or entry.aktenzeichen is None:
            return False
        if cleaned_title.split("/")[0] == entry.aktenzeichen.split("/")[0]:
            return True
        if entry.aktenzeichen in cleaned_title.replace("/ ", "/"):
            return True

        return False

    @staticmethod
    def _nbsps_to_spaces(s: str) -> str:
        needle = b"\xc2\xa0"
        while needle in s.encode("utf-8"):
            s = s.encode("utf-8").replace(needle, b" ").decode("utf-8")

        return s

    @staticmethod
    def _remove_duplicate_spaces(s: str) -> str:
        while "  " in s:
            s = s.replace("  ", " ")
        return s

    def _normalize_text(self, s: str) -> str:
        """Normalize common issues: NBSPs, zero-width chars, and UTF-8/Latin-1 mojibake."""
        if s is None:
            return s
        # Normalize NBSPs to regular spaces and remove zero-width space
        try:
            s = self._nbsps_to_spaces(s)
        except Exception:
            pass
        s = s.replace("\u202f", " ").replace("\u200b", "")
        # Fix typical mojibake (e.g., 'MÃ¤rz' -> 'März')
        if "Ã" in s or "Â" in s:
            try:
                s = s.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
            except Exception:
                pass
        return self._remove_duplicate_spaces(s).strip()

    def list(self, land: Land, plz: str = "") -> Iterator[Union[RawList, RawEntry, ObjektEntry, RawAnhang]]:
        params = {"button": "Suchen", "all": "1"}

        data = {
            "ger_name": "-- Alle Amtsgerichte --",
            "order_by": "2",
            "land_abk": land.short,
            "ger_id": "0",
            "az1": "",
            "az2": "",
            "az3": "",
            "az4": "",
            "art": "",
            "obj": "",
            "str": "",
            "hnr": "",
            "plz": plz,
            "ort": "",
            "ortsteil": "",
            "vtermin": "",
            "btermin": "",
        }

        response = self._session.post(self.endpoints.index, params=params, data=data, timeout=self._timeout)
        response.raise_for_status()
        last_raw_list = RawList(content=response.content)
        yield last_raw_list

        soup = BeautifulSoup(self._decode_html(response.content), "html.parser")
        table_rows = list(self._parse_html_table(soup))
        self._logger.info(f'Found {len(table_rows)} rows for "{land.name}".')

        # Prepare entries and collect detail URLs
        entries_to_fetch = []
        immediate_entries = []
        for rows in table_rows:
            entry = ObjektEntry(land_short=land.short, raw_list_sha256=last_raw_list.sha256)
            if "zvg_id" in rows.keys():
                entry.zvg_id = rows["zvg_id"]

            for td_content in rows.get("Aktenzeichen", []):
                for aktenzeichen_regex in [self._aktenzeichen_regex_1, self._aktenzeichen_regex_2]:
                    match = aktenzeichen_regex.search(td_content)
                    if match is not None:
                        entry.aktenzeichen = match.group(0)
                        break
            if "Amtsgericht" in rows.keys():
                entry.amtsgericht = self._normalize_text(" ".join(rows["Amtsgericht"]))
            if "Objekt/Lage" in rows.keys():
                raw_ol = " ".join(rows["Objekt/Lage"])
                entry.objekt_lage = self._normalize_text(raw_ol)
                entry.adresse = self._address_parser.parse(entry.objekt_lage)
                if entry.adresse is None:
                    self._logger.warning(f"Could not parse address out of: {entry.objekt_lage}")
            if "Verkehrswert in €" in rows.keys():
                entry.verkehrswert_in_cent = self._verkehrswert_parser.cents(rows["Verkehrswert in €"][0])
            if "Termin" in rows.keys():
                termin_raw = " ".join(rows["Termin"])
                entry.termin_as_str = self._normalize_text(termin_raw)
                if "wurde aufgehoben" in entry.termin_as_str:
                    entry.wurde_aufgehoben = True
                else:
                    # Strip "Uhr" suffix and parse
                    t_for_parse = re.sub(r"\s*Uhr\.?", "", entry.termin_as_str, flags=re.IGNORECASE).strip()
                    try:
                        entry.termin_as_date = self._versteigerungs_termin_parser.to_datetime(t_for_parse)
                    except ValueError:
                        self._logger.warning(f"Cannot parse date {repr(entry.termin_as_str)}.")

            for key, tds in rows.items():
                for td_content in tds if isinstance(tds, list) else []:
                    match = self._aktualisierung_regex.search(td_content)
                    if match:
                        entry.letzte_aktualisierung = datetime.datetime(
                            year=int(match.group("year"), 10),
                            month=int(match.group("month"), 10),
                            day=int(match.group("day"), 10),
                            hour=int(match.group("hour"), 10),
                            minute=int(match.group("minute"), 10),
                        )
                        continue

            if not entry.any:
                continue

            if entry.zvg_id:
                entries_to_fetch.append(entry)
            else:
                immediate_entries.append(entry)

        # Yield entries without details immediately
        for e in immediate_entries:
            yield e

        # Fetch details concurrently for remaining entries
        def _fetch_details(e: ObjektEntry):
            url = f"{self._base_url}/index.php?button=showZvg&zvg_id={e.zvg_id}&land_abk={land.short}"
            resp = self._session.get(
                url,
                headers={"Referer": f"{self._base_url}/index.php?button=Suchen"},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            raw_entry = RawEntry(content=resp.content)
            e.raw_entry_sha256 = raw_entry.sha256
            anhaenge = []
            if resp.content[0:10] == b"\n<!DOCTYPE":
                for new_entry in self._parse_details(e, resp.content):
                    if isinstance(new_entry, ObjektEntry):
                        e = new_entry
                    elif isinstance(new_entry, RawAnhang):
                        anhaenge.append(new_entry)
                    else:
                        raise NotImplementedError
            else:
                self._logger.error(f"Response not valid {e}, could not : {resp.content[:200]}")
            return e, raw_entry, anhaenge

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = [executor.submit(_fetch_details, e) for e in entries_to_fetch]
            for fut in as_completed(futures):
                try:
                    e, raw_entry, anhaenge = fut.result()
                    yield raw_entry
                    for a in anhaenge:
                        yield a
                    yield e
                except Exception as ex:
                    self._logger.warning(f"Skip entry due to detail fetch error: {ex}")
