#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Optional, List


class Sha256Mixin:
    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass
class Land:
    short: str
    name: str


@dataclass
class RawList(Sha256Mixin):
    content: bytes


@dataclass
class RawAnhang(Sha256Mixin):
    content: bytes


@dataclass
class RawEntry(Sha256Mixin):
    content: bytes


@dataclass
class ScraperRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    list_sha256s: List[str] = field(default_factory=list)
    entry_sha256s: List[str] = field(default_factory=list)
    anhang_sha256s: List[str] = field(default_factory=list)
    scraper_started: datetime.datetime = field(default_factory=datetime.datetime.now)
    scraper_finished: Optional[datetime.datetime] = None
    scraped_entries: int = 0
    new_file_count: int = 0


@dataclass
class Addresse:
    strasse: str
    plz: str
    ort: str
    stadtteil: Optional[str] = None


@dataclass
class ObjektEntry:
    land_short: str
    raw_list_sha256: str
    raw_entry_sha256: Optional[str] = None
    anhang_sha256s: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    letzte_aktualisierung: Optional[datetime.datetime] = None
    aktenzeichen: Optional[str] = None
    zvg_id: Optional[int] = None
    amtsgericht: Optional[str] = None
    objekt_lage: Optional[str] = None
    verkehrswert_in_cent: Optional[int] = None
    wurde_aufgehoben: bool = False
    termin_as_str: Optional[str] = None
    termin_as_date: Optional[datetime.datetime] = None
    grundbuch: Optional[str] = None
    art_der_versteigerung: Optional[str] = None
    ort_der_versteigerung: Optional[str] = None
    beschreibung: Optional[str] = None
    informationen_zum_glaeubiger: Optional[str] = None
    adresse: Optional[Addresse] = None

    @property
    def any(self) -> bool:
        return not all(e is None for e in [self.letzte_aktualisierung, self.aktenzeichen, self.zvg_id])
