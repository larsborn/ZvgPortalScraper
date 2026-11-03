#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import re
from typing import Optional

from zvg_portal.model import Addresse


class VerkehrswertParser:
    """Reads the Verkehrswert out of a portal cell.

    The previous implementation took the first run of ``[\\d,.]`` in the string
    and decided it had cents only if ``s[-3]`` was a separator. Four shapes in
    live data defeated that, all of them silently:

    - ``1) 285.000,002) 19.000,00`` — a multi-object listing whose values are
      separated by ``<br/>`` inside ONE ``<p>`` rather than one ``<p>`` each,
      so the next item's ``2)`` fused onto the decimals. ``,002`` is not two
      decimals, so the whole thing was read as whole euros: €285,000,002
      instead of €285,000 (by/48861, by/48930).
    - ``102.000,000 €`` — the portal itself wrote three decimals. Same 1000x
      inflation (rp/3876).
    - ``Grundbuch von Uelsen Blatt 1787 lfd.Nr. 13 (11): 30.000,00 €`` — prose
      before the amount, so the first numeric run was the Blatt number and the
      value came out as €1,787 (ni/13564).

    So: collect every number-ish token, prefer one that a currency marker
    follows, and decide the decimal separator per token rather than by
    position. A German amount never has three decimal places, so a longer
    fraction is truncated rather than promoted into the integer part.
    """

    # A number plus the separators inside it, optionally ending in the "no
    # cents" dash the portal uses ("48.600,- €", "450,-- EUR").
    _TOKEN = re.compile(r"\d[\d.,]*-{0,2}")
    # A bare run of digits with no separator and fewer than this many digits is
    # an ordinal, not a price: "Objekt 1:", "Lfd. Nr. 1", "BV-Nr. 2". The old
    # parser excluded them by accident, via a {4,20} length bound on its one
    # regex; dropping that bound without replacing it made "Objekt 1: 14.000,00"
    # parse as €1. Such a token is only accepted when a currency marker follows
    # it, which is proof enough that it is the amount.
    _MIN_BARE_DIGITS = 4
    # Currency right after a token is the strongest signal that it is the
    # amount and not a Blatt number, a house number or a Flurstück.
    _CURRENCY = re.compile(r"\s*(?:€|EUR\b|EURO\b)", re.IGNORECASE)

    MAX_DECIMALS = 2

    def cents(self, s: str) -> Optional[int]:
        """First token that reads as a stated amount.

        "Formatted or currency-adjacent, in document order" rather than
        "currency-adjacent wins outright": preferring currency jumped past the
        correct first value in cells that gloss a breakdown afterwards —
        "Gesamt: 11.250,00 Einzelwerte: lfd. Nr. 9: 1.615,00€" took the 1.615,
        and "501.000,-- davon entfaellt auf Zubehoer: 8.000,-- €" took the 8.000.

        A bare integer is an ordinal ("Objekt 1", "Blatt 1787") unless a
        currency marker follows it, which is what rescues "450,-- EUR".
        """
        if not s:
            return None
        fallback = None
        for match in self._TOKEN.finditer(s):
            token = match.group(0)
            # "1)" / "2)" enumerate the objects in a multi-value listing.
            # Only a bare one- or two-digit number counts as a marker —
            # "285.000,002)" is a fused value, not item 285000.
            if s[match.end() : match.end() + 1] == ")" and token.isdigit() and len(token) <= 2:
                continue
            value = self._token_to_cents(token)
            if value is None:
                continue
            core = token.strip(".,-")
            formatted = ("." in core) or ("," in core)
            if formatted or self._CURRENCY.match(s, match.end()):
                return value
            # Last resort only: a long bare number, which is what the old
            # parser's {4,20} bound would have accepted.
            if fallback is None and core.isdigit() and len(core) >= self._MIN_BARE_DIGITS:
                fallback = value
        return fallback

    @classmethod
    def _token_to_cents(cls, token: str) -> Optional[int]:
        token = token.rstrip()
        # "48.600,-", "450,--", "125.000,--" all mean "and no cents".
        token = re.sub(r"[.,]?-{1,2}$", "", token)
        token = token.strip(".,")
        if not token or not token[0].isdigit():
            return None

        dot, comma = token.rfind("."), token.rfind(",")
        if dot >= 0 and comma >= 0:
            # Both present: the one that comes last is the decimal separator.
            sep = max(dot, comma)
        elif dot >= 0 or comma >= 0:
            sep = max(dot, comma)
            # A lone separator followed by exactly three digits is a thousands
            # group ("256.000"), not a fraction.
            if len(token) - sep - 1 == 3:
                sep = -1
        else:
            sep = -1

        if sep < 0:
            whole, frac = token, ""
        else:
            whole, frac = token[:sep], token[sep + 1 :]
            # "285.000,002" is a fused value, "102.000,000" a portal typo.
            # Either way the euros are what precede the separator.
            frac = frac[: cls.MAX_DECIMALS]

        digits = whole.replace(".", "").replace(",", "")
        if not digits.isdigit():
            return None
        frac = (frac + "00")[: cls.MAX_DECIMALS] if frac else "00"
        if not frac.isdigit():
            return None
        return int(digits, 10) * 100 + int(frac, 10)


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
        # Walk patterns once; a "real" match (strasse contains a letter) wins
        # immediately. If only placeholder-strasse matches show up (e.g. the
        # portal emits `.` or `-` for unknown streets), fall back to the first
        # of those and keep the PLZ/Ort/Stadtteil — better partial location
        # data than nothing.
        placeholder_match = None
        for r in self._regexes:
            m = r.search(s)
            if not m:
                continue
            strasse = m.group("strasse").strip()
            if self._STRASSE_HAS_LETTER.search(strasse):
                return self._build_addresse(m, strasse)
            if placeholder_match is None:
                placeholder_match = m
        if placeholder_match is not None:
            return self._build_addresse(placeholder_match, None)
        return None

    def _build_addresse(self, m, strasse: Optional[str]) -> Optional[Addresse]:
        # '00000' is the portal's placeholder for "PLZ unknown" — same idea as
        # '.'/'-' for strasse. Treat it as None so SQL queries can filter it
        # out with IS NULL rather than a literal string compare.
        plz_val = m.group("plz").strip()
        plz = None if plz_val == "00000" else plz_val
        ort_val = m.group("ort")
        ort = ort_val.strip() if ort_val else None
        stadtteil = None
        try:
            stadtteil_val = m.group("stadtteil")
            if stadtteil_val:
                stadtteil = stadtteil_val.strip()
        except IndexError:
            pass
        if strasse is None and plz is None and ort is None and stadtteil is None:
            return None
        return Addresse(plz=plz, strasse=strasse, ort=ort, stadtteil=stadtteil)


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
