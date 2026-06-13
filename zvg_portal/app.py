#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import locale
import logging
import os
import platform
import signal
import threading

import requests
import requests.adapters

__service__ = "ZvgPortalScraper"
__version__ = "1.0.0"

from zvg_portal.model import ObjektEntry, RawAnhang, RawEntry, RawList, ScraperRun
from zvg_portal.nsq_util import ClientSideCertificate, Nsq
from zvg_portal.repository import RawRepository
from zvg_portal.runner import parse_interval, run_loop
from zvg_portal.scraper import ZvgPortal
from zvg_portal.utils import ConsoleHandler, CustomEncoder


def configure_locale(logger: logging.Logger) -> None:
    for locale_name in ("de_DE.UTF-8", "de_DE"):
        try:
            locale.setlocale(locale.LC_ALL, locale_name)
            return
        except locale.Error:
            continue
    logger.warning("German locale is unavailable; falling back to process default locale.")


def format_currency_eur(cents: int) -> str:
    amount = cents / 100
    try:
        return locale.currency(amount)
    except ValueError:
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--print-stats", action="store_true")
    parser.add_argument("--print-entries", action="store_true")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "https://www.zvg-portal.de"))
    parser.add_argument("--nsqd-address", default=os.getenv("NSQD_ADDRESS", "127.0.0.1"))
    parser.add_argument("--nsqd-port", default=os.getenv("NSQD_PORT", "4151"), type=int)
    parser.add_argument("--client-side-crt", default=os.getenv("CLIENT_SIDE_CRT"))
    parser.add_argument("--client-side-key", default=os.getenv("CLIENT_SIDE_KEY"))
    parser.add_argument(
        "--raw-data-directory",
        default=os.path.realpath(os.getenv("RAW_DATA_DIRECTORY", os.path.join(os.path.dirname(__file__), "..", "raw"))),
    )
    parser.add_argument(
        "--user-agent",
        default=f"{__service__}/{__version__} (python-requests {requests.__version__}) "
        f"{platform.system()} ({platform.release()})",
    )
    parser.add_argument(
        "--interval",
        default=os.getenv("INTERVAL"),
        help="If set, run continuously: sleep this duration between iterations. "
        "Format: '90s', '30m', '6h', '1h30m', or plain integer seconds. "
        "When unset (default), the scraper runs once and exits.",
    )
    args = parser.parse_args()

    logger = logging.getLogger(__service__)
    logger.handlers.append(ConsoleHandler())
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    configure_locale(logger)
    logger.debug(f"Using User-Agent string: {args.user_agent}")
    cert = None
    if args.client_side_crt or args.client_side_key:
        assert os.path.exists(args.client_side_crt)
        assert os.path.exists(args.client_side_key)
        cert = ClientSideCertificate(crt_path=args.client_side_crt, key_path=args.client_side_key)
    nsq = Nsq(args.nsqd_address, args.nsqd_port, cert)
    zvg_portal = ZvgPortal(logger, args.user_agent, args.base_url)

    if args.print_stats:
        for land in zvg_portal.get_laender():
            entries = [entry for entry in zvg_portal.list(land) if isinstance(entry, ObjektEntry)]
            if len(entries) == 0:
                continue
            total_cents = sum(entry.verkehrswert_in_cent for entry in entries if entry.verkehrswert_in_cent)
            logger.info(
                f"{len(entries)} Zwangsversteigerungen in {land.name}, "
                f"Verkehrswertsumme: {format_currency_eur(total_cents)}"
            )
            by_price = sorted(
                (entry for entry in entries if entry.verkehrswert_in_cent), key=lambda e: e.verkehrswert_in_cent
            )
            print(json.dumps(by_price[0], indent=4, cls=CustomEncoder, sort_keys=True))
            print(f"{zvg_portal.endpoints.show_details}&zvg_id={by_price[0].zvg_id}&land_abk={land.short}")
            print(json.dumps(by_price[-1], indent=4, cls=CustomEncoder, sort_keys=True))
            print(f"{zvg_portal.endpoints.show_details}&zvg_id={by_price[-1].zvg_id}&land_abk={land.short}")

    raw_repository = RawRepository(args.raw_data_directory)

    def scrape_once():
        run = ScraperRun()
        for land in zvg_portal.get_laender():
            entries = zvg_portal.list(land)
            for entry in entries:
                if isinstance(entry, ObjektEntry):
                    run.scraped_entries += 1
                    if args.print_entries:
                        print(json.dumps(entry, indent=4, cls=CustomEncoder, sort_keys=True))
                    dumped_data = json.dumps(entry, cls=CustomEncoder, sort_keys=True)
                    data = json.loads(dumped_data)
                    data["inserted_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    data["_key"] = hashlib.sha256(dumped_data.encode("utf-8")).hexdigest()[0:12]
                    nsq.publish("zvg_entries", json.dumps(data, sort_keys=True))
                elif isinstance(entry, RawList):
                    if raw_repository.store(entry.content):
                        run.new_file_count += 1
                    run.list_sha256s.append(entry.sha256)
                elif isinstance(entry, RawEntry):
                    if raw_repository.store(entry.content):
                        run.new_file_count += 1
                    run.entry_sha256s.append(entry.sha256)
                elif isinstance(entry, RawAnhang):
                    if raw_repository.store(entry.content):
                        run.new_file_count += 1
                    run.anhang_sha256s.append(entry.sha256)
                else:
                    raise NotImplementedError(f"Unknown type: {type(entry)}")
        run.scraper_finished = datetime.datetime.now(datetime.timezone.utc)
        nsq.publish("zvg_scraper_runs", json.dumps(run, cls=CustomEncoder, sort_keys=True))
        print(json.dumps(run, indent=4, cls=CustomEncoder, sort_keys=True))

    if args.interval is None:
        scrape_once()
        return

    interval_seconds = parse_interval(args.interval)
    stop_event = threading.Event()

    def _request_stop(signum, _frame):
        logger.info(f"received signal {signum}, shutting down after current iteration")
        stop_event.set()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    logger.info(f"daemon mode: scraping every {interval_seconds}s (with exponential backoff on failure)")
    run_loop(scrape_once, interval_seconds, logger, stop_event)


if __name__ == "__main__":
    main()
