#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os


class RawRepository:
    def __init__(self, dir_name: str):
        assert dir_name
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        assert os.path.isdir(dir_name)

        self._dir_name = dir_name

    def store(self, content: bytes) -> bool:
        sha256 = hashlib.sha256(content).hexdigest()
        dir_name = os.path.join(self._dir_name, sha256[0:2])
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        dir_name = os.path.join(self._dir_name, sha256[0:2], sha256[2:4])
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        dir_name = os.path.join(self._dir_name, sha256[0:2], sha256[2:4], sha256[4:6])
        if not os.path.exists(dir_name):
            os.mkdir(dir_name)
        path = os.path.join(dir_name, sha256)
        if os.path.exists(path):
            size_in_bytes = os.stat(path).st_size
            if size_in_bytes:
                assert size_in_bytes == len(content)
                return False
        with open(path, 'wb') as fp:
            fp.write(content)
        return True
