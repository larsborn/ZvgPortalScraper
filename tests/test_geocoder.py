#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import unittest
from unittest.mock import MagicMock

import requests

from zvg_portal.geocoder import (
    GeocodingResult,
    NominatimClient,
    _parse_nominatim_response,
    build_queries,
    cascading_geocode,
)


def _logger():
    return logging.getLogger("test_geocoder")


class TestParseNominatimResponse(unittest.TestCase):
    def test_empty_list_returns_none(self):
        self.assertIsNone(_parse_nominatim_response([]))

    def test_first_result_parsed(self):
        self.assertEqual(
            _parse_nominatim_response([{"lat": "48.137154", "lon": "11.576124"}]),
            (48.137154, 11.576124),
        )

    def test_non_list_returns_none(self):
        self.assertIsNone(_parse_nominatim_response({"error": "x"}))
        self.assertIsNone(_parse_nominatim_response(None))

    def test_missing_lat_lon_returns_none(self):
        self.assertIsNone(_parse_nominatim_response([{"foo": "bar"}]))

    def test_unparseable_floats_returns_none(self):
        self.assertIsNone(_parse_nominatim_response([{"lat": "abc", "lon": "11.5"}]))


class TestBuildQueries(unittest.TestCase):
    def test_full_address_yields_ok_plus_fallback(self):
        queries = build_queries("Hauptstr. 1", "80331", "München", "Altstadt")
        self.assertEqual(
            queries,
            [
                ("Hauptstr. 1, 80331 München, Altstadt, Deutschland", "OK"),
                ("80331 München, Deutschland", "PLZ_FALLBACK"),
            ],
        )

    def test_full_address_without_stadtteil(self):
        queries = build_queries("Hauptstr. 1", "80331", "München", None)
        self.assertEqual(
            queries,
            [
                ("Hauptstr. 1, 80331 München, Deutschland", "OK"),
                ("80331 München, Deutschland", "PLZ_FALLBACK"),
            ],
        )

    def test_no_strasse_yields_only_fallback(self):
        self.assertEqual(
            build_queries(None, "80331", "München", None),
            [("80331 München, Deutschland", "PLZ_FALLBACK")],
        )

    def test_only_plz(self):
        self.assertEqual(
            build_queries(None, "80331", None, None),
            [("80331, Deutschland", "PLZ_FALLBACK")],
        )

    def test_only_ort(self):
        self.assertEqual(
            build_queries(None, None, "München", None),
            [("München, Deutschland", "PLZ_FALLBACK")],
        )

    def test_strasse_alone_is_not_enough(self):
        # Just a street name with no PLZ/ort isn't worth pinging Nominatim with.
        self.assertEqual(build_queries("Hauptstr. 1", None, None, None), [])

    def test_nothing_at_all(self):
        self.assertEqual(build_queries(None, None, None, None), [])


class TestCascadingGeocode(unittest.TestCase):
    def setUp(self):
        self.client = MagicMock(spec=NominatimClient)

    def test_full_address_hit_marks_ok(self):
        self.client.geocode.return_value = (48.137, 11.576)
        result = cascading_geocode("Hauptstr. 1", "80331", "München", None, self.client, _logger())
        self.assertEqual(result, GeocodingResult(48.137, 11.576, "OK"))
        self.assertEqual(self.client.geocode.call_count, 1)

    def test_full_address_miss_falls_back_to_plz(self):
        self.client.geocode.side_effect = [None, (48.137, 11.576)]
        result = cascading_geocode("Hauptstr. 1", "80331", "München", None, self.client, _logger())
        self.assertEqual(result, GeocodingResult(48.137, 11.576, "PLZ_FALLBACK"))
        self.assertEqual(self.client.geocode.call_count, 2)

    def test_all_miss_marks_not_found(self):
        self.client.geocode.return_value = None
        result = cascading_geocode("Hauptstr. 1", "80331", "München", None, self.client, _logger())
        self.assertEqual(result, GeocodingResult(None, None, "NOT_FOUND"))
        self.assertEqual(self.client.geocode.call_count, 2)

    def test_request_exception_marks_retry_and_stops(self):
        self.client.geocode.side_effect = requests.ConnectionError("network down")
        result = cascading_geocode("Hauptstr. 1", "80331", "München", None, self.client, _logger())
        self.assertEqual(result, GeocodingResult(None, None, "ERROR_RETRY"))
        # Don't waste a second query when the first errored out
        self.assertEqual(self.client.geocode.call_count, 1)

    def test_no_data_marks_skipped_without_calling_client(self):
        result = cascading_geocode(None, None, None, None, self.client, _logger())
        self.assertEqual(result, GeocodingResult(None, None, "SKIPPED"))
        self.client.geocode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
