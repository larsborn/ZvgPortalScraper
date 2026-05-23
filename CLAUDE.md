# Notes for Claude

Project-specific context discovered while working in this repo. Read alongside `README.md` (which targets human operators).

## Test framework: stdlib `unittest` only

- **Do not introduce `pytest`** as a dependency. The user has explicitly declined it.
- Tests live in `tests/` and use `unittest.TestCase`. For table-driven cases, use `with self.subTest(...):` — never `pytest.mark.parametrize`.
- Run the full suite via `python -m unittest discover -s tests -v` from the repo root.
- Run a single module via `python -m unittest tests.<module> -v` (e.g. `tests.test_runner`).

### Pre-existing broken tests on `main`

As of 2026-05-23 the existing test suite has 7 failing tests, all due to drift between code and tests — not regressions from in-flight work:

- `tests/test_IdFactory.py` — calls `ObjektEntry(land_short="de", ...)` but `ObjektEntry.__init__` now requires `raw_list_sha256`.
- `tests/test_VersteigerungsTerminParser.py::test_negativeDay` — expects negative years to parse; the current parser rejects them.

When verifying new test work, prefer `python -m unittest tests.<your_module>` so these pre-existing failures don't pollute the result.

## File conventions for tests

Every test file in `tests/` follows this shape:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import unittest

from zvg_portal.something import Something


class SomethingTest(unittest.TestCase):
    def test_x(self):
        ...


if __name__ == "__main__":
    unittest.main()
```

Match this when adding new test files.

## Formatting / pre-commit

- `pre-commit` runs `black` and `isort` (configured in `pyproject.toml`, line length 120, target Python 3.9, isort profile `black`).
- Hooks are wired via `.pre-commit-config.yaml` and run on `git commit`.
- **Never** bypass with `--no-verify`. If a hook reformats your file, re-stage and commit again.
- Manual format: `pre-commit run --files <paths>` or `pre-commit run --all-files`.

## Git on Windows

The user runs Windows + bash. Use `git -C P:/Scraper/ZvgPortal <command>` (or whatever the working directory is) instead of `cd <path> && git ...` — `cd && git` triggers manual approval prompts in this environment.

## Application architecture

`zvg_portal/` is a small package:

- `app.py` — CLI entry. Builds the `ZvgPortal` client, NSQ publisher, raw-file repository, runs one scrape iteration (or, with `--interval`, loops via `runner.run_loop`).
- `scraper.py` — `ZvgPortal` class: HTTP session, HTML scraping/parsing of the search results and detail pages. Uses `ThreadPoolExecutor` for parallel detail fetches.
- `parser.py` — German-locale parsers: addresses, money (Verkehrswert), auction dates (Versteigerungstermin).
- `model.py` — Dataclasses: `Land`, `ObjektEntry`, `RawList`, `RawEntry`, `RawAnhang`, `ScraperRun`. `ObjektEntry` requires `raw_list_sha256` at construction time.
- `repository.py` — `RawRepository`: persists raw HTML/attachment bytes to disk by content hash.
- `nsq_util.py` — Thin NSQ HTTP publisher wrapping the nsqd `/pub` endpoint. Supports client-side TLS certs.
- `runner.py` — `parse_interval()` duration parser and `run_loop()` daemon loop (pure, stdlib-only, no I/O).
- `utils.py` — `ConsoleHandler` (logging) and `CustomEncoder` (JSON encoding for dataclasses + datetime).

## Operational modes

- **One-shot (default):** `python zvg_portal/app.py [...]` iterates all Länder once and exits. This is what cron/`docker run --rm`/K8s CronJobs use.
- **Daemon (`--interval`):** added 2026-05-23. `python zvg_portal/app.py --interval 6h [...]` scrapes, sleeps `interval`, scrapes, repeats. Exponential backoff (cap 16×) on consecutive failures. SIGTERM/SIGINT triggers a clean shutdown after the current iteration (or aborts mid-sleep). See `docs/superpowers/specs/2026-05-23-continuous-scraper-design.md` for the design rationale.

All CLI flags have environment-variable equivalents (`BASE_URL`, `NSQD_ADDRESS`, `NSQD_PORT`, `CLIENT_SIDE_CRT`, `CLIENT_SIDE_KEY`, `RAW_DATA_DIRECTORY`, `INTERVAL`) — used heavily by the Docker image.

## Docker

- `Dockerfile` is based on `python:3.13-slim-bookworm`, generates `de_DE`/`de_DE.UTF-8` locales, runs as unprivileged `scraper` user.
- Published image: `ghcr.io/larsborn/zvgportalscraper` (auto-built on version tags).
- `VOLUME /data/raw` and `RAW_DATA_DIRECTORY=/data/raw` baked in.
- The image runs `app.py` as its CMD; pass flags or env vars on `docker run` / in `docker-compose.yml`.

## German locale

`app.py` calls `locale.setlocale(locale.LC_ALL, "de_DE")` at startup. The Docker image generates these locales explicitly. Don't remove this — `parser.py` relies on German month names ("März", "Dezember") and currency formatting.

## Plans and specs

In-progress / completed design artifacts live under `docs/superpowers/`:

- `specs/YYYY-MM-DD-<topic>-design.md` — approved designs.
- `plans/YYYY-MM-DD-<topic>.md` — step-by-step implementation plans.

These are untracked by default — the user has chosen not to commit them. Treat them as scratch space for the current task.
