#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import hashlib
import json
import os

from pyArango.collection import Collection
from pyArango.connection import Connection
from pyArango.database import Database
from pyArango.theExceptions import UniqueConstrainViolation

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--arangodb-url', default=os.environ.get('ARANGODB_URL'))
    parser.add_argument('--arangodb-database', default=os.environ.get('ARANGODB_DATABASE'))
    parser.add_argument('--arangodb-username', default=os.environ.get('ARANGODB_USERNAME'))
    parser.add_argument('--arangodb-password', default=os.environ.get('ARANGODB_PASSWORD'))
    parser.add_argument(
        '--arangodb-client-certificate-path',
        default=os.environ.get('ARANGODB_CLIENT_CERTIFICATE_PATH'),
    )
    parser.add_argument('--arangodb-client-key-path', default=os.environ.get('ARANGODB_CLIENT_KEY_PATH'))
    args = parser.parse_args()
    connection = Connection(
        arangoURL=args.arangodb_url,
        username=args.arangodb_username,
        password=args.arangodb_password,
        cert=(args.arangodb_client_certificate_path, args.arangodb_client_key_path),
    )
    db = connection[args.arangodb_database]  # type: Database
    collection = db['zvg_entries']  # type: Collection
    all_rows = list(collection.fetchAll())
    print(f'Found a total of {len(all_rows)} rows.')
    for i, entry in enumerate(all_rows):
        data = entry.getStore()
        if len(data['_key']) == 12:
            continue
        del data['_id']
        old_key = data['_key']
        del data['_key']
        del data['_rev']

        inserted_at = None
        if 'inserted_at' in data.keys():
            inserted_at = data['inserted_at']
            del data['inserted_at']
        dumped_data = json.dumps(data, sort_keys=True).encode('utf-8')
        new_key = hashlib.sha256(dumped_data).hexdigest()[:12]
        data['_key'] = new_key
        if inserted_at:
            data['inserted_at'] = inserted_at
        new_doc = collection.createDocument(data)
        print(f'{old_key} -> {new_key}')
        # print('.', end='' if (i + 1) % 100 else '\n')
        try:
            new_doc.save()
        except UniqueConstrainViolation:
            pass
        entry.delete()
