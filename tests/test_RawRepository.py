#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os
import tempfile
import unittest

from zvg_portal.repository import RawRepository, guess_extension

PDF_HEADER = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
JPG_HEADER = b"\xff\xd8\xff\xe0\x00\x10JFIF"
PNG_HEADER = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
GIF87_HEADER = b"GIF87a\x00\x00"
GIF89_HEADER = b"GIF89a\x00\x00"
HTML_DOCTYPE = b"<!DOCTYPE html><html><body>x</body></html>"
HTML_BARE = b"<html><body>x</body></html>"
HTML_WHITESPACE = b"\n   <!DOCTYPE html><html></html>"
HTML_BOM = b"\xef\xbb\xbf<!DOCTYPE html><html></html>"
UNKNOWN = b"\x00\x01\x02\x03\x04unknown garbage"


class TestGuessExtension(unittest.TestCase):
    def test_pdf(self):
        self.assertEqual(guess_extension(PDF_HEADER), ".pdf")

    def test_jpg(self):
        self.assertEqual(guess_extension(JPG_HEADER), ".jpg")

    def test_png(self):
        self.assertEqual(guess_extension(PNG_HEADER), ".png")

    def test_gif87(self):
        self.assertEqual(guess_extension(GIF87_HEADER), ".gif")

    def test_gif89(self):
        self.assertEqual(guess_extension(GIF89_HEADER), ".gif")

    def test_html_doctype(self):
        self.assertEqual(guess_extension(HTML_DOCTYPE), ".html")

    def test_html_bare_tag(self):
        self.assertEqual(guess_extension(HTML_BARE), ".html")

    def test_html_leading_whitespace(self):
        self.assertEqual(guess_extension(HTML_WHITESPACE), ".html")

    def test_html_utf8_bom(self):
        self.assertEqual(guess_extension(HTML_BOM), ".html")

    def test_unknown_returns_empty(self):
        self.assertEqual(guess_extension(UNKNOWN), "")

    def test_empty_returns_empty(self):
        self.assertEqual(guess_extension(b""), "")


class TestRawRepository(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo_dir = self._tmp.name
        self.repo = RawRepository(self.repo_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def _expected_path(self, content: bytes, ext: str) -> str:
        sha = hashlib.sha256(content).hexdigest()
        return os.path.join(self.repo_dir, sha[0:2], sha[2:4], sha[4:6], sha + ext)

    def test_pdf_gets_pdf_extension(self):
        self.assertTrue(self.repo.store(PDF_HEADER))
        self.assertTrue(os.path.exists(self._expected_path(PDF_HEADER, ".pdf")))

    def test_jpg_gets_jpg_extension(self):
        self.assertTrue(self.repo.store(JPG_HEADER))
        self.assertTrue(os.path.exists(self._expected_path(JPG_HEADER, ".jpg")))

    def test_html_gets_html_extension(self):
        self.assertTrue(self.repo.store(HTML_DOCTYPE))
        self.assertTrue(os.path.exists(self._expected_path(HTML_DOCTYPE, ".html")))

    def test_unknown_content_has_no_extension(self):
        self.assertTrue(self.repo.store(UNKNOWN))
        self.assertTrue(os.path.exists(self._expected_path(UNKNOWN, "")))

    def test_same_content_no_op_on_second_store(self):
        self.assertTrue(self.repo.store(PDF_HEADER))
        self.assertFalse(self.repo.store(PDF_HEADER))

    def test_legacy_extension_less_file_is_recognized(self):
        # Simulate a file that was written before this change shipped: stored
        # without an extension. A subsequent store of the same content should
        # be a no-op (we should NOT write a new <sha>.pdf alongside it).
        sha = hashlib.sha256(PDF_HEADER).hexdigest()
        legacy_dir = os.path.join(self.repo_dir, sha[0:2], sha[2:4], sha[4:6])
        os.makedirs(legacy_dir, exist_ok=True)
        legacy_path = os.path.join(legacy_dir, sha)
        with open(legacy_path, "wb") as fp:
            fp.write(PDF_HEADER)

        result = self.repo.store(PDF_HEADER)
        self.assertFalse(result, "duplicate of legacy file should be a no-op")
        new_path = self._expected_path(PDF_HEADER, ".pdf")
        self.assertFalse(
            os.path.exists(new_path),
            "should not create a duplicate at the new-style path",
        )

    def test_different_content_produces_different_files(self):
        self.assertTrue(self.repo.store(PDF_HEADER))
        self.assertTrue(self.repo.store(JPG_HEADER))
        self.assertTrue(os.path.exists(self._expected_path(PDF_HEADER, ".pdf")))
        self.assertTrue(os.path.exists(self._expected_path(JPG_HEADER, ".jpg")))


if __name__ == "__main__":
    unittest.main()
