#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Geocode addresses in zvg_entry via Nominatim, store lat/lng in MariaDB.

Long-running polling worker. Queries `zvg_entry` for rows whose
`geocoding_status` is NULL (never tried) or `ERROR_RETRY` (transient
failure last time), geocodes via the public Nominatim service with a
cascading fallback (full address → PLZ+Ort → PLZ/Ort alone), writes
lat/lng/geocoded_at/geocoding_status back. Sleeps when nothing's queued.

Public Nominatim's usage policy requires:
- A contact identifier (e.g. email) in the User-Agent.
- ≤ 1 request per second.

Both are enforced here.
"""

import argparse
import dataclasses
import datetime
import logging
import os
import signal
import threading
import time
from typing import List, Optional, Tuple

import pymysql
import requests

__service__ = "zvg_geocoder"
__version__ = "0.1.0"


SCHEMA_STATEMENTS = [
    """
    ALTER TABLE zvg_entry
        ADD COLUMN IF NOT EXISTS lat              DECIMAL(9, 6) NULL,
        ADD COLUMN IF NOT EXISTS lng              DECIMAL(9, 6) NULL,
        ADD COLUMN IF NOT EXISTS geocoded_at      DATETIME      NULL,
        ADD COLUMN IF NOT EXISTS geocoding_status VARCHAR(32)   NULL
    """,
    "CREATE INDEX IF NOT EXISTS idx_geocoded_at      ON zvg_entry (geocoded_at)",
    "CREATE INDEX IF NOT EXISTS idx_has_coords       ON zvg_entry (lat, lng)",
    "CREATE INDEX IF NOT EXISTS idx_geocoding_status ON zvg_entry (geocoding_status)",
]


@dataclasses.dataclass
class GeocodingResult:
    lat: Optional[float]
    lng: Optional[float]
    status: str  # OK | PLZ_FALLBACK | NOT_FOUND | SKIPPED | ERROR_RETRY


def _parse_nominatim_response(payload) -> Optional[Tuple[float, float]]:
    """Return (lat, lng) for the first Nominatim result, or None if empty/bad."""
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    try:
        return float(first["lat"]), float(first["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def build_queries(
    strasse: Optional[str],
    plz: Optional[str],
    ort: Optional[str],
    stadtteil: Optional[str],
) -> List[Tuple[str, str]]:
    """Return progressively-broader (query_string, success_status) tuples.

    `success_status` is the value to write into `geocoding_status` if THAT
    particular query is the one that hits — `OK` for a full-address match,
    `PLZ_FALLBACK` for coarser geocoding.
    """
    queries: List[Tuple[str, str]] = []
    if strasse and plz and ort:
        parts = [strasse, f"{plz} {ort}"]
        if stadtteil:
            parts.append(stadtteil)
        parts.append("Deutschland")
        queries.append((", ".join(parts), "OK"))
    if plz and ort:
        queries.append((f"{plz} {ort}, Deutschland", "PLZ_FALLBACK"))
    elif plz:
        queries.append((f"{plz}, Deutschland", "PLZ_FALLBACK"))
    elif ort:
        queries.append((f"{ort}, Deutschland", "PLZ_FALLBACK"))
    return queries


class NominatimClient:
    """Rate-limited HTTP client for the Nominatim `/search` endpoint."""

    def __init__(
        self,
        user_agent: str,
        contact: str,
        base_url: str = "https://nominatim.openstreetmap.org",
        min_interval_seconds: float = 1.05,
        timeout_seconds: int = 30,
    ):
        self._session = requests.Session()
        # The contact is required by Nominatim's usage policy.
        self._session.headers["User-Agent"] = f"{user_agent} ({contact})"
        self._base_url = base_url.rstrip("/")
        self._min_interval_seconds = min_interval_seconds
        self._timeout_seconds = timeout_seconds
        self._last_call_monotonic = 0.0

    def geocode(self, query: str) -> Optional[Tuple[float, float]]:
        self._wait_for_rate_limit()
        response = self._session.get(
            f"{self._base_url}/search",
            params={
                "q": query,
                "format": "json",
                "limit": "1",
                "countrycodes": "de",
                "addressdetails": "0",
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        return _parse_nominatim_response(response.json())

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_call_monotonic
        if elapsed < self._min_interval_seconds:
            time.sleep(self._min_interval_seconds - elapsed)
        self._last_call_monotonic = time.monotonic()


def cascading_geocode(
    strasse: Optional[str],
    plz: Optional[str],
    ort: Optional[str],
    stadtteil: Optional[str],
    client: NominatimClient,
    logger: logging.Logger,
) -> GeocodingResult:
    queries = build_queries(strasse, plz, ort, stadtteil)
    if not queries:
        return GeocodingResult(None, None, "SKIPPED")
    for query, status in queries:
        try:
            coords = client.geocode(query)
        except requests.RequestException:
            logger.exception(f"Nominatim error for query: {query!r}")
            return GeocodingResult(None, None, "ERROR_RETRY")
        if coords:
            return GeocodingResult(coords[0], coords[1], status)
    return GeocodingResult(None, None, "NOT_FOUND")


class ZvgGeocoderApp:
    def __init__(
        self,
        logger: logging.Logger,
        connection,
        client: NominatimClient,
        batch_size: int = 50,
        idle_sleep_seconds: int = 60,
    ):
        self._logger = logger
        self._conn = connection
        self._client = client
        self._batch_size = batch_size
        self._idle_sleep_seconds = idle_sleep_seconds

    def apply_schema(self) -> None:
        with self._conn.cursor() as cur:
            for stmt in SCHEMA_STATEMENTS:
                cur.execute(stmt)
        self._conn.commit()
        self._logger.info(f"applied {len(SCHEMA_STATEMENTS)} schema statement(s)")

    def run(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            batch = self._fetch_batch()
            if not batch:
                self._logger.info(f"nothing to geocode; sleeping {self._idle_sleep_seconds}s")
                if stop_event.wait(self._idle_sleep_seconds):
                    break
                continue
            self._logger.info(f"geocoding batch of {len(batch)} entries")
            for row in batch:
                if stop_event.is_set():
                    return
                key, strasse, plz, ort, stadtteil = row
                result = cascading_geocode(strasse, plz, ort, stadtteil, self._client, self._logger)
                self._update_row(key, result)
                self._logger.debug(
                    f"{key} -> {result.status} "
                    f"({result.lat}, {result.lng}) "
                    f"[strasse={strasse!r}, plz={plz!r}, ort={ort!r}]"
                )

    def _fetch_batch(self):
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT `_key`, adresse_strasse, adresse_plz, adresse_ort, adresse_stadtteil
                FROM zvg_entry
                WHERE geocoding_status IS NULL OR geocoding_status = 'ERROR_RETRY'
                ORDER BY inserted_at DESC
                LIMIT %s
                """,
                (self._batch_size,),
            )
            return cur.fetchall()

    def _update_row(self, key: str, result: GeocodingResult) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        with self._conn.cursor() as cur:
            cur.execute(
                """
                UPDATE zvg_entry
                SET lat = %s, lng = %s, geocoded_at = %s, geocoding_status = %s
                WHERE `_key` = %s
                """,
                (result.lat, result.lng, now, result.status, key),
            )
        self._conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--mariadb-host", default=os.getenv("MARIADB_HOST", "mariadb"))
    parser.add_argument("--mariadb-port", default=os.getenv("MARIADB_PORT", "3306"), type=int)
    parser.add_argument("--mariadb-user", default=os.getenv("MARIADB_USER"))
    parser.add_argument("--mariadb-password", default=os.getenv("MARIADB_PASSWORD"))
    parser.add_argument("--mariadb-database", default=os.getenv("MARIADB_DATABASE", "zvg"))
    parser.add_argument(
        "--nominatim-base-url",
        default=os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"),
    )
    parser.add_argument(
        "--contact-email",
        default=os.getenv("GEOCODER_CONTACT_EMAIL"),
        help="Required: an address Nominatim operators can reach you at.",
    )
    parser.add_argument(
        "--rate-limit-seconds",
        default=os.getenv("RATE_LIMIT_SECONDS", "1.05"),
        type=float,
    )
    parser.add_argument(
        "--batch-size",
        default=os.getenv("BATCH_SIZE", "50"),
        type=int,
    )
    parser.add_argument(
        "--idle-sleep-seconds",
        default=os.getenv("IDLE_SLEEP_SECONDS", "60"),
        type=int,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__service__)
    logger.info(f"Starting {__service__}/{__version__}")

    if not args.mariadb_user or args.mariadb_password is None:
        parser.error("--mariadb-user and --mariadb-password are required (env: MARIADB_USER, MARIADB_PASSWORD)")
    if not args.contact_email:
        parser.error(
            "--contact-email is required (env: GEOCODER_CONTACT_EMAIL) — "
            "Nominatim's public usage policy requires a contact in the User-Agent"
        )

    connection = pymysql.connect(
        host=args.mariadb_host,
        port=args.mariadb_port,
        user=args.mariadb_user,
        password=args.mariadb_password,
        database=args.mariadb_database,
        charset="utf8mb4",
        autocommit=False,
    )
    client = NominatimClient(
        user_agent=f"{__service__}/{__version__}",
        contact=args.contact_email,
        base_url=args.nominatim_base_url,
        min_interval_seconds=args.rate_limit_seconds,
    )
    app = ZvgGeocoderApp(
        logger=logger,
        connection=connection,
        client=client,
        batch_size=args.batch_size,
        idle_sleep_seconds=args.idle_sleep_seconds,
    )

    stop_event = threading.Event()

    def _request_stop(signum, _frame):
        logger.info(f"received signal {signum}, shutting down after current row")
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    app.apply_schema()
    app.run(stop_event)
    logger.info("shutdown complete")


if __name__ == "__main__":
    main()
