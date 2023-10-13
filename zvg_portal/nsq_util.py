#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict

import requests


class Nsq:
    def __init__(self, logger: logging.Logger, nsqd_address: str, nsqd_write_port: int = 4151):
        self._logger = logger
        self._nsqd_address = nsqd_address
        self._nsqd_write_port = nsqd_write_port
        self._session = requests.session()

    def publish_dict(self, topic: str, message: Dict) -> None:
        return self.publish(topic, json.dumps(message))

    def publish(self, topic: str, message: str) -> None:
        self.publish_bytes(topic, message.encode('utf-8'))

    def publish_bytes(self, topic: str, message: bytes) -> None:
        response = self._session.post(
            F'http://{self._nsqd_address}:{self._nsqd_write_port}/pub?topic={topic}',
            data=message
        )
        response.raise_for_status()
