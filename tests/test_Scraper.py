#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import unittest

from zvg_portal.model import Land, ObjektEntry, RawAnhang, RawList
from zvg_portal.scraper import ZvgPortal


class FakeResponse:
    def __init__(self, content=b''):
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
        return FakeResponse(b'attachment-content')

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return FakeResponse(b'<html><table></table></html>')


class ScraperTest(unittest.TestCase):
    def _portal(self):
        logger = logging.getLogger(f'test.{self.id()}')
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        return ZvgPortal(logger, 'test-agent', 'https://example.test')

    def test_parse_details_downloads_attachment_for_any_land(self):
        portal = self._portal()
        fake_session = FakeSession()
        portal._session = fake_session
        entry = ObjektEntry(land_short='by', raw_list_sha256='raw-list')
        html = b'''
            <html><body>
                <a href="?button=showAnhang&land_abk=by&file_id=12&zvg_id=345">PDF</a>
                <table><tr><td>Aktenzeichen:</td><td>0001 K 0001/2024</td></tr></table>
            </body></html>
        '''

        parsed = list(portal._parse_details(entry, html))

        self.assertIsInstance(parsed[0], RawAnhang)
        self.assertIs(parsed[-1], entry)
        self.assertEqual([parsed[0].sha256], entry.anhang_sha256s)
        self.assertEqual(1, len(fake_session.get_calls))
        self.assertIn('land_abk=by', fake_session.get_calls[0][0])

    def test_parse_details_without_table_returns_entry(self):
        portal = self._portal()
        entry = ObjektEntry(land_short='by', raw_list_sha256='raw-list')

        parsed = list(portal._parse_details(entry, b'<html><body>No table</body></html>'))

        self.assertEqual([entry], parsed)

    def test_list_uses_configured_session(self):
        portal = self._portal()
        fake_session = FakeSession()
        portal._session = fake_session

        parsed = list(portal.list(Land(short='be', name='Berlin'), plz='10115'))

        self.assertEqual(1, len(fake_session.post_calls))
        self.assertIsInstance(parsed[0], RawList)


if __name__ == '__main__':
    unittest.main()
