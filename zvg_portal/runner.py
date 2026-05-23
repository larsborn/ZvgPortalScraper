"""Loop runner for the ZvgPortal scraper. Pure; no I/O."""

import re

_INTERVAL_TOKEN = re.compile(r"(\d+)([smh])")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}


def parse_interval(spec: str) -> int:
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
