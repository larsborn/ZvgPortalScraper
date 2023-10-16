#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import hashlib
import json
import os
from datetime import datetime

from pyArango.collection import Collection
from pyArango.connection import Connection
from pyArango.database import Database
from pyArango.theExceptions import UniqueConstrainViolation

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('json_file_name')
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
    for line in open(args.json_file_name, 'r'):
        data = json.loads(line)
        dumped_data = json.dumps(data, sort_keys=True).encode('utf-8')
        new_key = hashlib.sha256(dumped_data).hexdigest()[:12]
        data['_key'] = new_key
        if 'inserted_at' not in data.keys():
            data['inserted_at'] = datetime.utcnow().isoformat()
        new_doc = collection.createDocument(data)
        try:
            new_doc.save()
            print(new_doc['_key'])
        except UniqueConstrainViolation:
            pass
