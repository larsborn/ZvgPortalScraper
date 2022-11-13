#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import unittest

from zvg_portal.model import ObjektEntry
from zvg_portal.utils import IdFactory


class IdFactoryTest(unittest.TestCase):
    def test_sameIdOnDifferentObjects(self):
        id1 = IdFactory().from_objekt(ObjektEntry(land_short='de'))
        id2 = IdFactory().from_objekt(ObjektEntry(land_short='de'))
        self.assertEqual(id1, id2)

    def test_sameIdOnDifferentObjectsWithMultipleFields(self):
        id1 = IdFactory().from_objekt(ObjektEntry(land_short='de', zvg_id=123, objekt_lage='test'))
        id2 = IdFactory().from_objekt(ObjektEntry(land_short='de', zvg_id=123, objekt_lage='test'))
        self.assertEqual(id1, id2)

    def test_differentIds(self):
        id1 = IdFactory().from_objekt(ObjektEntry(land_short='de', zvg_id=345, objekt_lage='test'))
        id2 = IdFactory().from_objekt(ObjektEntry(land_short='de', zvg_id=123, objekt_lage='test'))
        self.assertNotEqual(id1, id2)

    def test_sameForSameDates(self):
        id1 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0),
        ))
        id2 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0),
        ))
        self.assertEqual(id1, id2)

    def test_differentForDifferentDates(self):
        id1 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0),
        ))
        id2 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=2, day=1, hour=0, minute=0),
        ))
        self.assertNotEqual(id1, id2)

    def test_differentIfCanceled(self):
        id1 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=1, day=1, hour=0, minute=0),
        ))
        id2 = IdFactory().from_objekt(ObjektEntry(
            land_short='de',
            termin_as_date=datetime.datetime(year=2022, month=2, day=1, hour=0, minute=0),
            wurde_aufgehoben=True
        ))
        self.assertNotEqual(id1, id2)


if __name__ == "__main__":
    unittest.main()
