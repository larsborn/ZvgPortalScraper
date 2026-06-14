#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import re
from typing import Optional

from zvg_portal.model import Addresse


class VerkehrswertParser:
    def __init__(self):
        self._r = re.compile(r"[\d,.]{4,20}")

    def cents(self, s: str) -> Optional[int]:
        match = self._r.search(s)
        if not match:
            return
        betrag_str = match.group(0)
        if betrag_str[-3] in [",", "."]:
            cents = int(betrag_str[-2:], 10)
            betrag_without_cents = betrag_str[:-3]
        else:
            cents = 0
            betrag_without_cents = betrag_str
        euro_str = betrag_without_cents.replace(".", "").replace(",", "")
        return int(euro_str, 10) * 100 + cents


class AddressParser:
    # A real street must contain at least one letter (German alphabet incl.
    # umlauts/ß). Anything matching strasse but failing this check is a
    # placeholder like `.` or `--` that the portal sometimes emits when the
    # street is unknown — better to fall through to the next pattern (and
    # ultimately store NULL) than to capture the sentinel.
    _STRASSE_HAS_LETTER = re.compile(r"[A-Za-zäöüÄÖÜß]")

    def __init__(self):
        self._regexes = [
            re.compile(
                r'(?P<strasse>[äüöÄÜÖß (),a-zA-Z0-9-".]+), '
                r"(?P<plz>\d{5}) "
                r"(?P<ort>[äüöÄÜÖß a-zA-Z0-9-.]+), "
                r"(?P<stadtteil>[äüöÄÜÖß a-zA-Z0-9-.]+)"
            ),
            re.compile(r'(?P<strasse>[äüöÄÜÖß (),a-zA-Z0-9-."]+), (?P<plz>\d{5}) (?P<ort>[äüöÄÜÖß a-zA-Z0-9-.]+)'),
            re.compile(
                r"(?P<strasse>[^,;]+)\s*,\s*" r"(?P<plz>\d{5})\s*;" r"(?P<ort>[^,;]+)" r"(?:,\s*(?P<stadtteil>[^,;]+))?"
            ),
            # Handle formats with a colon separator, e.g., "Description: Street, PLZ Ort"
            re.compile(
                r":\s*(?P<strasse>[^,]+?)\s*,\s*"
                r"(?P<plz>\d{5})\s*"
                r"(?P<ort>[^,;]*)"  # Ort is optional here
            ),
            # Permissive fallback for multi-house-number streets ("Hauptstr. 9, 9a, ...")
            # and PLZ '00000' (placeholder used by some Länder for unknown postal codes).
            # Must be last — only fires when the stricter patterns above don't match.
            re.compile(
                r":\s*"
                r"(?P<strasse>.+?)"  # strasse: anything (commas allowed)
                r"\s*,\s*"
                r"(?P<plz>\d{5})"
                r"(?:\s+(?P<ort>[^,]+?))?"  # optional ort
                r"(?:\s*,\s*(?P<stadtteil>[^,]+))?"
                r"\s*$"
            ),
        ]

    def parse(self, s: str) -> Optional[Addresse]:
        for r in self._regexes:
            m = r.search(s)
            if not m:
                continue
            strasse = m.group("strasse").strip()
            if not self._STRASSE_HAS_LETTER.search(strasse):
                # Match is structurally OK but strasse is a placeholder (e.g. '.').
                # Treat as a non-match and try the next pattern.
                continue
            ort_val = m.group("ort")
            ret = Addresse(
                strasse=strasse,
                plz=m.group("plz").strip(),
                ort=ort_val.strip() if ort_val else None,
            )
            try:
                stadtteil_val = m.group("stadtteil")
                if stadtteil_val:
                    ret.stadtteil = stadtteil_val.strip()
            except IndexError:
                pass
            return ret


class VersteigerungsTerminParser:
    _MONTHS = {
        "januar": 1,
        "februar": 2,
        "märz": 3,
        "maerz": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "dezember": 12,
    }

    _TERMIN_REGEX = re.compile(
        r"^\s*(?:[A-Za-zÄÖÜäöüß]+,\s*)?"
        r"(?P<day>\d{1,2})\.\s+"
        r"(?P<month>[A-Za-zÄÖÜäöüß]+)\s+"
        r"(?P<year>\d{4}),\s+"
        r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
        r"(?:\s+Uhr)?\s*$"
    )

    def to_datetime(self, s: str) -> Optional[datetime.datetime]:
        match = self._TERMIN_REGEX.match(s)
        if not match:
            return None

        month = self._MONTHS.get(match.group("month").casefold())
        if month is None:
            return None

        try:
            return datetime.datetime(
                year=int(match.group("year"), 10),
                month=month,
                day=int(match.group("day"), 10),
                hour=int(match.group("hour"), 10),
                minute=int(match.group("minute"), 10),
            )
        except ValueError:
            return None
