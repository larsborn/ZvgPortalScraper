"""Loop runner for the ZvgPortal scraper. Pure; no I/O."""

import logging
import re
import threading
from typing import Callable, Optional

_INTERVAL_TOKEN = re.compile(r"(\d+)([smh])")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}


def parse_interval(spec: Optional[str]) -> int:
    """Parse a human duration string into seconds.

    Accepts: '90s', '30m', '6h', '1h30m', '2h15m45s', or a plain integer (seconds).
    Raises ValueError on anything else.
    """
    if spec is None or spec == "":
        raise ValueError("interval must not be empty")
    if spec.isdigit():
        return int(spec)
    tokens = _INTERVAL_TOKEN.findall(spec)
    if not tokens:
        raise ValueError(f"cannot parse interval: {spec!r}")
    consumed = "".join(n + u for n, u in tokens)
    if consumed != spec:
        raise ValueError(f"cannot parse interval: {spec!r}")
    return sum(int(n) * _UNIT_SECONDS[u] for n, u in tokens)


_BACKOFF_CAP_DEFAULT = 4


def run_loop(
    scrape_once: Callable[[], None],
    interval_seconds: int,
    logger: logging.Logger,
    stop_event: threading.Event,
    sleep: Optional[Callable[[float], bool]] = None,
    backoff_cap: int = _BACKOFF_CAP_DEFAULT,
) -> None:
    """Run `scrape_once` in a loop until `stop_event` is set.

    Sleeps `interval_seconds * 2**min(consecutive_failures, backoff_cap)` between
    iterations. Logs and swallows any exception raised by `scrape_once`. Runs
    immediately on entry; sleep is only invoked between iterations.

    `sleep(seconds) -> bool`: should return True if the wait was interrupted by
    `stop_event` being set (matching `threading.Event.wait` semantics).
    """
    if sleep is None:
        sleep = stop_event.wait
    consecutive_failures = 0
    while not stop_event.is_set():
        try:
            scrape_once()
            consecutive_failures = 0
        except Exception:
            logger.exception("scrape iteration failed")
            consecutive_failures += 1
        if stop_event.is_set():
            break
        multiplier = 2 ** min(consecutive_failures, backoff_cap)
        if sleep(interval_seconds * multiplier):
            break
