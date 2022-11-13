#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import datetime
import hashlib
import json
import logging
from dataclasses import asdict
from typing import Optional

import requests.adapters
from urllib3 import Retry

from zvg_portal.model import ObjektEntry


class ConsoleHandler(logging.Handler):
    def emit(self, record):
        print('[%s] %s' % (record.levelname, record.msg))


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()


class CustomHTTPAdapter(requests.adapters.HTTPAdapter):
    def __init__(
            self,
            fixed_timeout: int = 5,
            retries: int = 3,
            backoff_factor: float = 0.3,
            status_forcelist=(500, 502, 504),
            pool_maxsize: Optional[int] = None
    ):
        self._fixed_timeout = fixed_timeout
        retry_strategy = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        kwargs = {'max_retries': retry_strategy}
        if pool_maxsize is not None:
            kwargs['pool_maxsize'] = pool_maxsize
        super().__init__(**kwargs)

    def send(self, *args, **kwargs):
        if kwargs['timeout'] is None:
            kwargs['timeout'] = self._fixed_timeout
        return super(CustomHTTPAdapter, self).send(*args, **kwargs)


class IdFactory:
    @staticmethod
    def from_objekt(objekt: ObjektEntry) -> str:
        return hashlib.sha256(
            json.dumps(asdict(objekt), indent=0, cls=CustomEncoder, sort_keys=True).encode('utf-8')
        ).hexdigest()[:8]
