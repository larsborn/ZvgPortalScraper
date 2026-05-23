#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consume NSQ topics published by the ZvgPortal scraper into MariaDB.

Subscribes to both `zvg_entries` (every scraped Versteigerung) and
`zvg_scraper_runs` (one per scrape iteration) and lands them in a relational
schema with the entry's content-hashed `_key` as the natural primary key. Run
as a long-lived container alongside an `nsqd` and a MariaDB instance.
"""

import argparse
import datetime
import logging
import os
from typing import Optional

from nsq2mariadb import Mapper, MariaDBConfig, Nsq2MariaDB, NsqConfig

__service__ = "zvg2mariadb"
__version__ = "0.1.0"


def _iso_to_datetime(value: Optional[str]) -> Optional[datetime.datetime]:
    """Parse an ISO-8601 string back into a datetime; pass through None."""
    if value is None:
        return None
    return datetime.datetime.fromisoformat(value)


class ZvgEntryMapper(Mapper):
    topic = "zvg_entries"
    schema_sql = """
        CREATE TABLE IF NOT EXISTS zvg_entry (
            `_key`                       CHAR(12)      NOT NULL,
            land_short                   CHAR(2)       NOT NULL,
            zvg_id                       BIGINT        NULL,
            aktenzeichen                 VARCHAR(64)   NULL,
            amtsgericht                  VARCHAR(255)  NULL,
            objekt_lage                  TEXT          NULL,
            verkehrswert_in_cent         BIGINT        NULL,
            wurde_aufgehoben             TINYINT(1)    NOT NULL DEFAULT 0,
            termin_as_str                VARCHAR(255)  NULL,
            termin_as_date               DATETIME      NULL,
            letzte_aktualisierung        DATETIME      NULL,
            grundbuch                    VARCHAR(255)  NULL,
            art_der_versteigerung        VARCHAR(255)  NULL,
            ort_der_versteigerung        VARCHAR(255)  NULL,
            beschreibung                 TEXT          NULL,
            informationen_zum_glaeubiger TEXT          NULL,
            adresse_strasse              VARCHAR(255)  NULL,
            adresse_plz                  CHAR(5)       NULL,
            adresse_ort                  VARCHAR(255)  NULL,
            adresse_stadtteil            VARCHAR(255)  NULL,
            raw_list_sha256              CHAR(64)      NOT NULL,
            raw_entry_sha256             CHAR(64)      NULL,
            inserted_at                  DATETIME      NOT NULL,
            PRIMARY KEY (`_key`),
            INDEX idx_land         (land_short),
            INDEX idx_zvg_id       (zvg_id),
            INDEX idx_termin       (termin_as_date),
            INDEX idx_plz          (adresse_plz),
            INDEX idx_aktenzeichen (aktenzeichen),
            INDEX idx_inserted     (inserted_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

        CREATE TABLE IF NOT EXISTS zvg_entry_url (
            entry_key  CHAR(12)      NOT NULL,
            position   SMALLINT      NOT NULL,
            url        VARCHAR(2048) NOT NULL,
            PRIMARY KEY (entry_key, position),
            CONSTRAINT fk_url_entry FOREIGN KEY (entry_key)
                REFERENCES zvg_entry(`_key`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

        CREATE TABLE IF NOT EXISTS zvg_entry_anhang (
            entry_key  CHAR(12)  NOT NULL,
            position   SMALLINT  NOT NULL,
            sha256     CHAR(64)  NOT NULL,
            PRIMARY KEY (entry_key, position),
            INDEX idx_sha (sha256),
            CONSTRAINT fk_anh_entry FOREIGN KEY (entry_key)
                REFERENCES zvg_entry(`_key`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    def transform(self, doc):
        adresse = doc.get("adresse") or {}
        yield "zvg_entry", {
            "_key": doc["_key"],
            "land_short": doc["land_short"],
            "zvg_id": doc.get("zvg_id"),
            "aktenzeichen": doc.get("aktenzeichen"),
            "amtsgericht": doc.get("amtsgericht"),
            "objekt_lage": doc.get("objekt_lage"),
            "verkehrswert_in_cent": doc.get("verkehrswert_in_cent"),
            "wurde_aufgehoben": 1 if doc.get("wurde_aufgehoben") else 0,
            "termin_as_str": doc.get("termin_as_str"),
            "termin_as_date": _iso_to_datetime(doc.get("termin_as_date")),
            "letzte_aktualisierung": _iso_to_datetime(doc.get("letzte_aktualisierung")),
            "grundbuch": doc.get("grundbuch"),
            "art_der_versteigerung": doc.get("art_der_versteigerung"),
            "ort_der_versteigerung": doc.get("ort_der_versteigerung"),
            "beschreibung": doc.get("beschreibung"),
            "informationen_zum_glaeubiger": doc.get("informationen_zum_glaeubiger"),
            "adresse_strasse": adresse.get("strasse"),
            "adresse_plz": adresse.get("plz"),
            "adresse_ort": adresse.get("ort"),
            "adresse_stadtteil": adresse.get("stadtteil"),
            "raw_list_sha256": doc["raw_list_sha256"],
            "raw_entry_sha256": doc.get("raw_entry_sha256"),
            "inserted_at": _iso_to_datetime(doc["inserted_at"]),
        }

        entry_key = doc["_key"]
        for i, url in enumerate(doc.get("urls") or []):
            yield "zvg_entry_url", {"entry_key": entry_key, "position": i, "url": url}
        for i, sha in enumerate(doc.get("anhang_sha256s") or []):
            yield "zvg_entry_anhang", {"entry_key": entry_key, "position": i, "sha256": sha}


class ZvgScraperRunMapper(Mapper):
    topic = "zvg_scraper_runs"
    schema_sql = """
        CREATE TABLE IF NOT EXISTS zvg_scraper_run (
            id               CHAR(36)  NOT NULL,
            scraper_started  DATETIME  NOT NULL,
            scraper_finished DATETIME  NULL,
            scraped_entries  INT       NOT NULL DEFAULT 0,
            new_file_count   INT       NOT NULL DEFAULT 0,
            PRIMARY KEY (id),
            INDEX idx_started (scraper_started)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    def transform(self, doc):
        yield "zvg_scraper_run", {
            "id": doc["id"],
            "scraper_started": _iso_to_datetime(doc["scraper_started"]),
            "scraper_finished": _iso_to_datetime(doc.get("scraper_finished")),
            "scraped_entries": doc.get("scraped_entries", 0),
            "new_file_count": doc.get("new_file_count", 0),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--mariadb-host", default=os.getenv("MARIADB_HOST", "mariadb"))
    parser.add_argument("--mariadb-port", default=os.getenv("MARIADB_PORT", "3306"), type=int)
    parser.add_argument("--mariadb-user", default=os.getenv("MARIADB_USER"))
    parser.add_argument("--mariadb-password", default=os.getenv("MARIADB_PASSWORD"))
    parser.add_argument("--mariadb-database", default=os.getenv("MARIADB_DATABASE", "zvg"))
    parser.add_argument("--nsqd-address", default=os.getenv("NSQD_ADDRESS", "nsq-nsqd-1"))
    parser.add_argument("--nsqd-tcp-port", default=os.getenv("NSQD_TCP_PORT", "4150"), type=int)
    parser.add_argument("--nsq-channel", default=os.getenv("NSQ_CHANNEL", __service__))
    parser.add_argument("--max-in-flight", default=os.getenv("NSQ_MAX_IN_FLIGHT", "1"), type=int)
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

    runner = Nsq2MariaDB(
        logger=logger,
        mariadb_config=MariaDBConfig(
            host=args.mariadb_host,
            port=args.mariadb_port,
            user=args.mariadb_user,
            password=args.mariadb_password,
            database=args.mariadb_database,
        ),
        nsq_config=NsqConfig(
            address=args.nsqd_address,
            port=args.nsqd_tcp_port,
            channel=args.nsq_channel,
            max_in_flight=args.max_in_flight,
        ),
        mappers=[ZvgEntryMapper(), ZvgScraperRunMapper()],
    )
    runner.run()


if __name__ == "__main__":
    main()
