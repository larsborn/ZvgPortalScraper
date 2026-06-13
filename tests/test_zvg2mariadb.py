#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import unittest

from zvg_portal.zvg2mariadb import ZvgEntryMapper, ZvgScraperRunMapper, _iso_to_datetime


def _full_entry_doc():
    return {
        "_key": "abc123def456",
        "inserted_at": "2026-05-23T14:23:45.123456",
        "land_short": "by",
        "zvg_id": 12345,
        "aktenzeichen": "2022 K 0123/0024",
        "amtsgericht": "Amtsgericht München",
        "objekt_lage": "Eigentumswohnung: Hauptstr. 1, 80331 München",
        "verkehrswert_in_cent": 50000000,
        "wurde_aufgehoben": False,
        "termin_as_str": "Donnerstag, 12. März 2026, 10:00 Uhr",
        "termin_as_date": "2026-03-12T10:00:00",
        "letzte_aktualisierung": "2026-05-20T12:34:00",
        "grundbuch": "Blatt 4711",
        "art_der_versteigerung": "Teilungsversteigerung",
        "ort_der_versteigerung": "Sitzungssaal A 101",
        "beschreibung": "Eigentumswohnung im 3. OG",
        "informationen_zum_glaeubiger": "Bank XY",
        "adresse": {
            "strasse": "Hauptstr. 1",
            "plz": "80331",
            "ort": "München",
            "stadtteil": "Altstadt-Lehel",
        },
        "raw_list_sha256": "a" * 64,
        "raw_entry_sha256": "b" * 64,
        "anhang_sha256s": ["c" * 64, "d" * 64],
        "urls": ["http://example.com/1", "http://example.com/2"],
    }


class TestIsoToDatetime(unittest.TestCase):
    def test_none_passes_through(self):
        self.assertIsNone(_iso_to_datetime(None))

    def test_full_iso_with_microseconds(self):
        self.assertEqual(
            _iso_to_datetime("2026-05-23T14:23:45.123456"),
            datetime.datetime(2026, 5, 23, 14, 23, 45, 123456),
        )

    def test_iso_without_microseconds(self):
        self.assertEqual(
            _iso_to_datetime("2026-03-12T10:00:00"),
            datetime.datetime(2026, 3, 12, 10, 0, 0),
        )

    def test_aware_iso_with_utc_offset(self):
        # Scraper publishes UTC-aware ISO strings (datetime.now(timezone.utc)).
        parsed = _iso_to_datetime("2026-06-14T08:15:30.123456+00:00")
        self.assertEqual(
            parsed,
            datetime.datetime(2026, 6, 14, 8, 15, 30, 123456, tzinfo=datetime.timezone.utc),
        )
        # pymysql will strftime this without tz, storing the UTC wall-clock value
        # in MariaDB's naive DATETIME column.
        self.assertIsNotNone(parsed.tzinfo)


class TestZvgEntryMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = ZvgEntryMapper()

    def test_topic_and_schema_present(self):
        self.assertEqual(self.mapper.topic, "zvg_entries")
        self.assertIn("CREATE TABLE IF NOT EXISTS zvg_entry", self.mapper.schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS zvg_entry_url", self.mapper.schema_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS zvg_entry_anhang", self.mapper.schema_sql)

    def test_full_entry_fans_out_three_tables(self):
        rows = list(self.mapper.transform(_full_entry_doc()))

        # 1 entry + 2 urls + 2 anhang = 5 rows
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            [r[0] for r in rows],
            [
                "zvg_entry",
                "zvg_entry_url",
                "zvg_entry_url",
                "zvg_entry_anhang",
                "zvg_entry_anhang",
            ],
        )

    def test_entry_row_field_mapping(self):
        rows = list(self.mapper.transform(_full_entry_doc()))
        _, row = rows[0]
        self.assertEqual(row["_key"], "abc123def456")
        self.assertEqual(row["land_short"], "by")
        self.assertEqual(row["zvg_id"], 12345)
        self.assertEqual(row["verkehrswert_in_cent"], 50000000)
        self.assertEqual(row["wurde_aufgehoben"], 0)  # False → 0 (TINYINT)
        self.assertEqual(row["termin_as_date"], datetime.datetime(2026, 3, 12, 10, 0, 0))
        self.assertEqual(row["inserted_at"], datetime.datetime(2026, 5, 23, 14, 23, 45, 123456))
        # Inlined Addresse columns:
        self.assertEqual(row["adresse_strasse"], "Hauptstr. 1")
        self.assertEqual(row["adresse_plz"], "80331")
        self.assertEqual(row["adresse_ort"], "München")
        self.assertEqual(row["adresse_stadtteil"], "Altstadt-Lehel")

    def test_url_rows_preserve_order_and_position(self):
        rows = list(self.mapper.transform(_full_entry_doc()))
        url_rows = [r for r in rows if r[0] == "zvg_entry_url"]
        self.assertEqual(
            url_rows[0][1],
            {
                "entry_key": "abc123def456",
                "position": 0,
                "url": "http://example.com/1",
            },
        )
        self.assertEqual(
            url_rows[1][1],
            {
                "entry_key": "abc123def456",
                "position": 1,
                "url": "http://example.com/2",
            },
        )

    def test_anhang_rows_preserve_order(self):
        rows = list(self.mapper.transform(_full_entry_doc()))
        anh_rows = [r for r in rows if r[0] == "zvg_entry_anhang"]
        self.assertEqual(
            anh_rows[0][1],
            {
                "entry_key": "abc123def456",
                "position": 0,
                "sha256": "c" * 64,
            },
        )
        self.assertEqual(
            anh_rows[1][1],
            {
                "entry_key": "abc123def456",
                "position": 1,
                "sha256": "d" * 64,
            },
        )

    def test_null_adresse_and_empty_lists(self):
        doc = _full_entry_doc()
        doc["adresse"] = None
        doc["urls"] = []
        doc["anhang_sha256s"] = []

        rows = list(self.mapper.transform(doc))

        # Only the parent row, no fanout
        self.assertEqual(len(rows), 1)
        _, row = rows[0]
        self.assertIsNone(row["adresse_strasse"])
        self.assertIsNone(row["adresse_plz"])
        self.assertIsNone(row["adresse_ort"])
        self.assertIsNone(row["adresse_stadtteil"])

    def test_minimal_entry_does_not_explode(self):
        # All optional fields missing or None — only the truly required ones present.
        doc = {
            "_key": "deadbeef0000",
            "land_short": "be",
            "raw_list_sha256": "0" * 64,
            "inserted_at": "2026-01-01T00:00:00",
        }
        rows = list(self.mapper.transform(doc))
        self.assertEqual(len(rows), 1)
        _, row = rows[0]
        self.assertEqual(row["_key"], "deadbeef0000")
        self.assertEqual(row["land_short"], "be")
        self.assertIsNone(row["zvg_id"])
        self.assertIsNone(row["aktenzeichen"])
        self.assertEqual(row["wurde_aufgehoben"], 0)
        self.assertEqual(row["inserted_at"], datetime.datetime(2026, 1, 1))

    def test_wurde_aufgehoben_true_becomes_1(self):
        doc = _full_entry_doc()
        doc["wurde_aufgehoben"] = True
        _, row = next(self.mapper.transform(doc))
        self.assertEqual(row["wurde_aufgehoben"], 1)


class TestZvgScraperRunMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = ZvgScraperRunMapper()

    def test_topic_and_schema(self):
        self.assertEqual(self.mapper.topic, "zvg_scraper_runs")
        self.assertIn("CREATE TABLE IF NOT EXISTS zvg_scraper_run", self.mapper.schema_sql)

    def test_full_run(self):
        doc = {
            "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
            "list_sha256s": ["a" * 64],  # framework ignores these (not in schema)
            "entry_sha256s": ["b" * 64],
            "anhang_sha256s": [],
            "scraper_started": "2026-05-23T14:00:00",
            "scraper_finished": "2026-05-23T14:23:45",
            "scraped_entries": 1234,
            "new_file_count": 5,
        }
        rows = list(self.mapper.transform(doc))
        self.assertEqual(len(rows), 1)
        table, row = rows[0]
        self.assertEqual(table, "zvg_scraper_run")
        self.assertEqual(row["id"], "7c9e6679-7425-40de-944b-e07fc1f90ae7")
        self.assertEqual(row["scraper_started"], datetime.datetime(2026, 5, 23, 14, 0, 0))
        self.assertEqual(row["scraper_finished"], datetime.datetime(2026, 5, 23, 14, 23, 45))
        self.assertEqual(row["scraped_entries"], 1234)
        self.assertEqual(row["new_file_count"], 5)

    def test_run_in_progress_has_no_finished_time(self):
        doc = {
            "id": "00000000-0000-0000-0000-000000000000",
            "scraper_started": "2026-05-23T14:00:00",
            "scraper_finished": None,
            "scraped_entries": 0,
            "new_file_count": 0,
        }
        _, row = next(self.mapper.transform(doc))
        self.assertIsNone(row["scraper_finished"])


if __name__ == "__main__":
    unittest.main()
