#!/usr/bin/env python3
import argparse
import json
import locale
import logging
import os
import platform
from dataclasses import asdict

import requests
import requests.adapters

__version__ = '1.0.0'

from zvg_portal.model import Land, ObjektEntry, RawList, RawEntry
from zvg_portal.scraper import ZvgPortal
from zvg_portal.utils import ConsoleHandler, CustomEncoder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--print-stats', action='store_true')
    parser.add_argument('--base-url', default=os.getenv('BASE_URL', 'https://www.zvg-portal.de'))
    parser.add_argument(
        '--user-agent',
        default=F'ZvgPortalScraper/{__version__} (python-requests {requests.__version__}) '
                F'{platform.system()} ({platform.release()})'
    )
    args = parser.parse_args()

    logger = logging.getLogger('ZvgPortalScraper')
    logger.handlers.append(ConsoleHandler())
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    locale.setlocale(locale.LC_ALL, 'de_DE')
    logger.debug(F'Using User-Agent string: {args.user_agent}')
    zvg_portal = ZvgPortal(logger, args.user_agent, args.base_url)

    if args.print_stats:
        for land in zvg_portal.get_laender():
            entries = [entry for entry in zvg_portal.list(land) if isinstance(entry, ObjektEntry)]
            if len(entries) == 0:
                continue
            total_cents = sum(entry.verkehrswert_in_cent for entry in entries if entry.verkehrswert_in_cent)
            logger.info(
                f'{len(entries)} Zwangsversteigerungen in {land.name}, '
                f'Verkehrswertsumme: {locale.currency(total_cents / 100)}'
            )
            by_price = sorted(
                (entry for entry in entries if entry.verkehrswert_in_cent),
                key=lambda e: e.verkehrswert_in_cent
            )
            print(json.dumps(asdict(by_price[0]), indent=4, cls=CustomEncoder, sort_keys=True))
            print(f'{zvg_portal.endpoints.show_details}&zvg_id={by_price[0].zvg_id}&land_abk={land.short}')
            print(json.dumps(asdict(by_price[-1]), indent=4, cls=CustomEncoder, sort_keys=True))
            print(f'{zvg_portal.endpoints.show_details}&zvg_id={by_price[-1].zvg_id}&land_abk={land.short}')

    entries = list(zvg_portal.list(Land(short='nw', name='NRW')))
    logger.info(f'Found {len(entries)} entries.')
    for entry in entries:
        if isinstance(entry, ObjektEntry):
            print(json.dumps(asdict(entry), indent=4, cls=CustomEncoder, sort_keys=True))
        elif isinstance(entry, RawList) or isinstance(entry, RawEntry):
            print(entry.sha256)


if __name__ == '__main__':
    main()
