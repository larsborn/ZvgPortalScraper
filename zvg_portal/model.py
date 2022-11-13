#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class Land:
    short: str
    name: str


@dataclass
class ObjektEntry:
    land_short: str
    letzte_aktualisierung: Optional[datetime.datetime] = None
    aktenzeichen: Optional[str] = None
    zvg_id: Optional[int] = None
    amtsgericht: Optional[str] = None
    objekt_lage: Optional[str] = None
    verkehrswert_in_cent: Optional[int] = None
    wurde_aufgehoben: bool = False
    termin_as_str: Optional[str] = None
    termin_as_date: Optional[datetime.datetime] = None

    @property
    def any(self) -> bool:
        return not all(e is None for e in [self.letzte_aktualisierung, self.aktenzeichen, self.zvg_id])
