#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os


def guess_extension(content: bytes) -> str:
    """Return a dotted extension based on the first bytes of ``content``.

    Returns '' for content the sniffer doesn't recognize. The set of detected
    types covers what the ZVG portal serves in practice: HTML for list/detail
    pages, PDF for the auction documents (Gutachten, Exposé, etc.), and
    JPG/PNG/GIF for Fotos.
    """
    if not content:
        return ""
    if content.startswith(b"%PDF"):
        return ".pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    # HTML — tolerate a UTF-8 BOM and/or leading whitespace before the tag.
    sample = content[:512].lstrip(b"\xef\xbb\xbf").lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return ".html"
    return ""


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

        ext = guess_extension(content)
        path = os.path.join(dir_name, sha256 + ext)
        # Also check the legacy extension-less filename so files written before
        # this change shipped don't trigger spurious re-downloads.
        legacy_path = os.path.join(dir_name, sha256)
        for candidate in (path, legacy_path):
            if os.path.exists(candidate):
                size_in_bytes = os.stat(candidate).st_size
                if size_in_bytes:
                    assert size_in_bytes == len(content)
                    return False
        with open(path, "wb") as fp:
            fp.write(content)
        return True
