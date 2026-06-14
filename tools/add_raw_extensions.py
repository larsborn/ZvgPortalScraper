#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rename existing raw files to add a content-type extension.

The scraper's RawRepository used to write files as bare SHA-256 hashes with
no extension. From v0.4.0 it writes `<sha256>.<ext>` based on a magic-byte
sniff (.pdf / .jpg / .png / .gif / .html, or no extension if unrecognized).
This one-shot script walks an existing raw directory and renames legacy
extension-less files to match the new naming.

Standalone — no project imports — so you can run it from anywhere with
Python 3.9+:

    python add_raw_extensions.py Z:/                # dry-run by default
    python add_raw_extensions.py Z:/ --apply        # actually rename

Already-extensioned files are left alone, so re-running is idempotent.
"""

import argparse
import sys
from pathlib import Path


def guess_extension(content: bytes) -> str:
    """Same magic-byte sniffer used by RawRepository.store()."""
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
    sample = content[:512].lstrip(b"\xef\xbb\xbf").lstrip().lower()
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return ".html"
    return ""


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("raw_dir", help="Path to the raw data directory (sharded by SHA-256 prefix)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename files. Without this, the script is a dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after processing this many files (0 = no limit). Useful for testing on a small subset first.",
    )
    args = parser.parse_args()

    root = Path(args.raw_dir)
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    by_ext: dict[str, int] = {}  # detected extension -> count of legacy files seen
    skipped_has_ext = 0
    skipped_unknown = 0
    renamed = 0
    processed = 0

    for path in root.rglob("*"):
        if args.limit and processed >= args.limit:
            break
        if not path.is_file():
            continue
        processed += 1
        if path.suffix:
            skipped_has_ext += 1
            continue
        try:
            with path.open("rb") as fp:
                header = fp.read(1024)
        except OSError as e:
            print(f"WARN: cannot read {path}: {e}", file=sys.stderr)
            continue
        ext = guess_extension(header)
        if not ext:
            skipped_unknown += 1
            continue
        by_ext[ext] = by_ext.get(ext, 0) + 1
        new_path = path.with_name(path.name + ext)
        if args.apply:
            try:
                path.rename(new_path)
            except OSError as e:
                print(f"WARN: cannot rename {path} -> {new_path}: {e}", file=sys.stderr)
                continue
        renamed += 1

    verb = "Renamed" if args.apply else "Would rename"
    print()
    print(f"Scanned:           {processed:>10} files")
    print(f"Already had ext:   {skipped_has_ext:>10} files (skipped)")
    print(f"Unknown content:   {skipped_unknown:>10} files (skipped)")
    print(f"{verb}:           {renamed:>10} files")
    if by_ext:
        print()
        print("By detected extension:")
        for ext, n in sorted(by_ext.items(), key=lambda x: -x[1]):
            print(f"  {ext:<6} {n:>10}")
    if not args.apply and renamed:
        print()
        print("Dry-run only. Re-run with --apply to perform the renames.")


if __name__ == "__main__":
    main()
