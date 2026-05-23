#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import threading
import unittest

from zvg_portal.runner import parse_interval, run_loop


class TestParseInterval(unittest.TestCase):
    def test_valid_specs(self):
        cases = [
            ("90s", 90),
            ("30m", 30 * 60),
            ("6h", 6 * 3600),
            ("1h30m", 1 * 3600 + 30 * 60),
            ("2h15m45s", 2 * 3600 + 15 * 60 + 45),
            ("21600", 21600),  # plain int → seconds
            ("0s", 0),
        ]
        for spec, expected_seconds in cases:
            with self.subTest(spec=spec):
                self.assertEqual(parse_interval(spec), expected_seconds)

    def test_invalid_specs_raise_value_error(self):
        bad_cases = [
            "",
            "6x",  # unknown unit
            "-1h",  # negative not allowed
            "1.5h",  # no decimals
            "h30m",  # leading unit without number
            "6 h",  # whitespace
            "6H",  # uppercase units not allowed
            "abc",
            "30m6",  # trailing number without unit
        ]
        for bad in bad_cases:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    parse_interval(bad)

    def test_none_raises(self):
        with self.assertRaises(ValueError):
            parse_interval(None)


class _FakeScrape:
    def __init__(self, stop_event, stop_after):
        self.calls = 0
        self._stop_event = stop_event
        self._stop_after = stop_after

    def __call__(self):
        self.calls += 1
        if self.calls >= self._stop_after:
            self._stop_event.set()


class _ScriptedScrape:
    """Each call uses the next outcome: 'ok' returns, 'fail' raises."""

    def __init__(self, outcomes, stop_event):
        self._outcomes = list(outcomes)
        self._stop_event = stop_event
        self.calls = 0

    def __call__(self):
        self.calls += 1
        outcome = self._outcomes[self.calls - 1]
        if self.calls >= len(self._outcomes):
            self._stop_event.set()
        if outcome == "fail":
            raise RuntimeError(f"boom #{self.calls}")


def _recording_sleep(durations):
    def _sleep(seconds):
        durations.append(seconds)
        return False  # mimics threading.Event.wait returning False (no signal)

    return _sleep


def _make_logger():
    return logging.getLogger("test_runner")


class TestRunLoop(unittest.TestCase):
    def test_runs_immediately_then_sleeps_interval(self):
        stop = threading.Event()
        fake = _FakeScrape(stop_event=stop, stop_after=2)
        durations = []

        run_loop(
            scrape_once=fake,
            interval_seconds=60,
            logger=_make_logger(),
            stop_event=stop,
            sleep=_recording_sleep(durations),
        )

        self.assertEqual(fake.calls, 2)
        # 2 iterations → at most 2 sleeps; first sleep must be the base interval
        self.assertEqual(durations[0], 60)

    def test_backoff_and_reset(self):
        stop = threading.Event()
        # Sequence: ok, fail, fail, ok, ok (stop after 5)
        scripted = _ScriptedScrape(["ok", "fail", "fail", "ok", "ok"], stop)
        durations = []

        run_loop(
            scrape_once=scripted,
            interval_seconds=10,
            logger=_make_logger(),
            stop_event=stop,
            sleep=_recording_sleep(durations),
        )

        self.assertEqual(scripted.calls, 5)
        # Sleeps happen BETWEEN iterations, so 4 sleeps for 5 calls.
        # After call 1 (ok)   → failures=0 → sleep 10*1  = 10
        # After call 2 (fail) → failures=1 → sleep 10*2  = 20
        # After call 3 (fail) → failures=2 → sleep 10*4  = 40
        # After call 4 (ok)   → failures=0 → sleep 10*1  = 10
        # Call 5 sets stop → no sleep after it.
        self.assertEqual(durations, [10, 20, 40, 10])

    def test_backoff_caps(self):
        stop = threading.Event()
        scripted = _ScriptedScrape(["fail"] * 7, stop)
        durations = []

        run_loop(
            scrape_once=scripted,
            interval_seconds=1,
            logger=_make_logger(),
            stop_event=stop,
            sleep=_recording_sleep(durations),
            backoff_cap=4,
        )

        # 7 failures → 6 sleeps in between
        # multipliers: 2, 4, 8, 16, 16, 16
        self.assertEqual(durations, [2, 4, 8, 16, 16, 16])


if __name__ == "__main__":
    unittest.main()
