#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from zvg_portal import scraper as scraper_module
from zvg_portal.model import Land, ObjektEntry, RawAnhang, RawList
from zvg_portal.scraper import ZvgPortal


class FakeResponse:
    def __init__(self, content=b""):
        self.content = content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.mounted = []
        self.get_calls = []
        self.post_calls = []

    def mount(self, prefix, adapter):
        self.mounted.append((prefix, adapter))

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(b"attachment-content")

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(b"<html><table></table></html>")


class ScraperTest(unittest.TestCase):
    def _portal(self):
        logger = logging.getLogger(f"test.{self.id()}")
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return ZvgPortal(logger, "test-agent", "https://example.test")

    def test_parse_details_downloads_attachment_for_any_land(self):
        portal = self._portal()
        fake_session = FakeSession()
        portal._session = fake_session
        entry = ObjektEntry(land_short="by", raw_list_sha256="raw-list")
        html = b"""
            <html><body>
                <a href="?button=showAnhang&land_abk=by&file_id=12&zvg_id=345">PDF</a>
                <table><tr><td>Aktenzeichen:</td><td>0001 K 0001/2024</td></tr></table>
            </body></html>
        """

        parsed = list(portal._parse_details(entry, html))

        self.assertIsInstance(parsed[0], RawAnhang)
        self.assertIs(parsed[-1], entry)
        self.assertEqual([parsed[0].sha256], entry.anhang_sha256s)
        self.assertEqual(1, len(fake_session.get_calls))
        self.assertIn("land_abk=by", fake_session.get_calls[0][0])

    def test_parse_details_without_table_returns_entry(self):
        portal = self._portal()
        entry = ObjektEntry(land_short="by", raw_list_sha256="raw-list")

        parsed = list(portal._parse_details(entry, b"<html><body>No table</body></html>"))

        self.assertEqual([entry], parsed)

    def test_list_bounds_detail_fetches_in_flight(self):
        """list() must not submit a whole Bundesland to the pool at once.

        The original code did `futures = [executor.submit(...) for e in
        entries_to_fetch]` and consumed them with `as_completed(futures)`.
        Two things then kept raw bytes alive far longer than necessary:

        1. the workers ran ahead of whoever consumes this generator, so
           finished results piled up inside their Futures, and
        2. the `futures` list held every Future - and so every detail page
           plus every attachment PDF - until the Bundesland was finished.

        With Nordrhein-Westfalen's ~1000 entries that was the bulk of a run's
        RSS, peaking near 1.8 GB. In Sep 2026 that peak was misread as a leak
        and "fixed" with a 1 GB container memory cap, which turned it into a
        crash loop: the process died at exactly the cap every ~90 s, 1278
        times over 32 h, and no scrape ever completed. It looked healthy the
        whole time - the failed allocation surfaced as a clean exit 0 with no
        OOM counter, and `restart: unless-stopped` kept the container "Up".

        So this test asserts the property that prevents all of that: work is
        submitted in a bounded window, while every entry is still delivered.
        """
        row_count = 20
        rows = "".join(
            f"<tr><td>Aktenzeichen:</td>"
            f'<td><a href="index.php?button=showZvg&zvg_id={i}&land_abk=by">{i}</a></td></tr>'
            for i in range(1, row_count + 1)
        )
        list_html = f"<html><body><table>{rows}</table></body></html>".encode("utf-8")
        detail_html = (
            b"\n<!DOCTYPE html><html><body><table>"
            b"<tr><td>Aktenzeichen:</td><td>0001 K 0001/2024</td></tr>"
            b"</table></body></html>"
        )

        class DetailSession(FakeSession):
            def get(self, url, **kwargs):
                self.get_calls.append((url, kwargs))
                return FakeResponse(detail_html)

            def post(self, url, **kwargs):
                self.post_calls.append((url, kwargs))
                return FakeResponse(list_html)

        created = []

        class RecordingExecutor(ThreadPoolExecutor):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.submitted = 0
                created.append(self)

            def submit(self, fn, *args, **kwargs):
                self.submitted += 1
                return super().submit(fn, *args, **kwargs)

        portal = self._portal()
        portal._session = DetailSession()
        portal._max_workers = 1  # window is max_workers * 2

        with mock.patch.object(scraper_module, "ThreadPoolExecutor", RecordingExecutor):
            produced = portal.list(Land(short="by", name="Bayern"))
            self.assertIsInstance(next(produced), RawList)
            next(produced)  # first detail payload: the pool is now running

            self.assertLessEqual(
                created[0].submitted,
                2,
                "detail fetches must be submitted in a bounded window, not all at once",
            )

            rest = list(produced)

        entries = [item for item in rest if isinstance(item, ObjektEntry)]
        self.assertEqual(row_count, len(entries), "every entry must still be delivered")
        self.assertEqual(row_count, created[0].submitted)

    def test_list_uses_configured_session(self):
        portal = self._portal()
        fake_session = FakeSession()
        portal._session = fake_session

        parsed = list(portal.list(Land(short="be", name="Berlin"), plz="10115"))

        self.assertEqual(1, len(fake_session.post_calls))
        self.assertIsInstance(parsed[0], RawList)


if __name__ == "__main__":
    unittest.main()
