#!/usr/bin/env python3
import argparse
import datetime
import hashlib
import json
import locale
import logging
import os
import platform

import requests
import requests.adapters

__version__ = '1.0.0'

from zvg_portal.model import ObjektEntry, RawList, RawEntry, ScraperRun, RawAnhang
from zvg_portal.nsq_util import Nsq, ClientSideCertificate
from zvg_portal.repository import RawRepository
from zvg_portal.scraper import ZvgPortal
from zvg_portal.utils import ConsoleHandler, CustomEncoder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--print-stats', action='store_true')
    parser.add_argument('--print-entries', action='store_true')
    parser.add_argument('--base-url', default=os.getenv('BASE_URL', 'https://www.zvg-portal.de'))
    parser.add_argument('--nsqd-address', default=os.getenv('NSQD_ADDRESS', '127.0.0.1'))
    parser.add_argument('--nsqd-port', default=os.getenv('NSQD_PORT', '4151'), type=int)
    parser.add_argument('--client-side-crt', default=os.getenv('CLIENT_SIDE_CRT'))
    parser.add_argument('--client-side-key', default=os.getenv('CLIENT_SIDE_KEY'))
    parser.add_argument(
        '--raw-data-directory',
        default=os.path.realpath(os.getenv('RAW_DATA_DIRECTORY', os.path.join(os.path.dirname(__file__), '..', 'raw')))
    )
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
                f'{len(entries)} Zwangsversteigerungen in {land.name}, '
                f'Verkehrswertsumme: {locale.currency(total_cents / 100)}'
            )
            by_price = sorted(
                (entry for entry in entries if entry.verkehrswert_in_cent),
                key=lambda e: e.verkehrswert_in_cent
            )
            print(json.dumps(by_price[0], indent=4, cls=CustomEncoder, sort_keys=True))
            print(f'{zvg_portal.endpoints.show_details}&zvg_id={by_price[0].zvg_id}&land_abk={land.short}')
            print(json.dumps(by_price[-1], indent=4, cls=CustomEncoder, sort_keys=True))
            print(f'{zvg_portal.endpoints.show_details}&zvg_id={by_price[-1].zvg_id}&land_abk={land.short}')

    raw_repository = RawRepository(args.raw_data_directory)
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
                data['inserted_at'] = datetime.datetime.now().isoformat()
                data['_key'] = hashlib.sha256(dumped_data.encode('utf-8')).hexdigest()[0:12]
                nsq.publish('zvg_entries', json.dumps(data, sort_keys=True))
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
                raise NotImplementedError(f'Unknown type: {type(entry)}')
    run.scraper_finished = datetime.datetime.now()
    nsq.publish('zvg_scraper_runs', json.dumps(run, cls=CustomEncoder, sort_keys=True))
    print(json.dumps(run, indent=4, cls=CustomEncoder, sort_keys=True))


if __name__ == '__main__':
    main()
