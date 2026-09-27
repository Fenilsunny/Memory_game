"""Offline tests: python -m unittest test_download -v

The end-to-end test runs download.py against a local HTTP server that
imitates the Dukascopy feed. The server reads the URL's month segment as
ZERO-BASED, so if download.py got the month wrong the test would fail.
"""

import datetime as dt
import http.server
import lzma
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import align
import download

HERE = Path(__file__).resolve().parent


def make_bi5(hour: dt.datetime, point: float, base: float, n: int = 120) -> bytes:
    """n ticks, 30s apart (so 2 per minute), price stepping by 1 point each tick."""
    rec = np.zeros(n, dtype=download.RECORD_DTYPE)
    rec["ms"] = np.arange(n) * 30_000
    bid = np.round((base + hour.hour * 0.001) * point) + np.arange(n)
    rec["bid"] = bid
    rec["ask"] = bid + 2
    rec["bid_volume"] = 1.5
    rec["ask_volume"] = 2.5
    return lzma.compress(rec.tobytes(), format=lzma.FORMAT_ALONE)


class FakeFeed(http.server.BaseHTTPRequestHandler):
    bases = {"EURUSD": 1.05, "GBPUSD": 1.25, "USDIDXUSD": 99.0}
    flaky_once = set()   # paths that fail with 503 the first time
    missing = set()      # (instrument, hour) that 404
    requests = []

    def do_GET(self):
        FakeFeed.requests.append(self.path)
        parts = self.path.strip("/").split("/")  # datafeed/INST/YYYY/MM/DD/HHh_ticks.bi5
        inst, y, m0, d, fname = parts[1], int(parts[2]), int(parts[3]), int(parts[4]), parts[5]
        if not 0 <= m0 <= 11:
            return self.send_error(400, "month must be zero-based")
        hour = dt.datetime(y, m0 + 1, d, int(fname[:2]))
        if self.path in FakeFeed.flaky_once:
            FakeFeed.flaky_once.discard(self.path)
            return self.send_error(503)
        if (inst, hour) in FakeFeed.missing:
            return self.send_error(404)
        body = make_bi5(hour, download.INSTRUMENTS[inst]["point"], self.bases[inst])
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class UnitTests(unittest.TestCase):
    def test_url_month_is_zero_based(self):
        u = download.hour_url("B", "EURUSD", dt.datetime(2025, 12, 1, 7))
        self.assertEqual(u, "B/EURUSD/2025/11/01/07h_ticks.bi5")
        u = download.hour_url("B", "EURUSD", dt.datetime(2026, 1, 15, 23))
        self.assertEqual(u, "B/EURUSD/2026/00/15/23h_ticks.bi5")

    def test_weekend_skip(self):
        closed = download.is_market_closed
        self.assertTrue(closed(dt.datetime(2025, 12, 6, 12)))   # Saturday
        self.assertTrue(closed(dt.datetime(2025, 12, 5, 22)))   # Friday after close
        self.assertFalse(closed(dt.datetime(2025, 12, 5, 21)))  # Friday before winter close
        self.assertTrue(closed(dt.datetime(2025, 12, 7, 20)))   # Sunday before open
        self.assertFalse(closed(dt.datetime(2025, 12, 7, 21)))  # Sunday summer open
        self.assertFalse(closed(dt.datetime(2025, 12, 3, 3)))   # Wednesday

    def test_month_hours_bounds(self):
        hours = download.month_hours("2025-12")
        self.assertEqual(hours[0], dt.datetime(2025, 12, 1, 0))
        self.assertEqual(hours[-1], dt.datetime(2025, 12, 31, 23))
        self.assertFalse(any(h.weekday() == 5 for h in hours))

    def test_decode_and_bars(self):
        hour = dt.datetime(2025, 12, 3, 10)
        ticks = download.ticks_for_hour(make_bi5(hour, 1e5, 1.05), hour, 1e5)
        self.assertEqual(len(ticks), 120)
        self.assertEqual(str(ticks.index.tz), "UTC")
        self.assertAlmostEqual(ticks["bid"].iloc[0], 1.06, places=6)
        self.assertAlmostEqual(ticks["ask"].iloc[0] - ticks["bid"].iloc[0], 2e-5, places=9)
        bars = download.to_1m_bars(ticks, "bid")
        self.assertEqual(len(bars), 60)
        first = bars.iloc[0]
        self.assertAlmostEqual(first["open"], 1.06, places=6)
        self.assertAlmostEqual(first["close"], 1.06001, places=6)
        self.assertEqual(first["ticks"], 2)
        self.assertAlmostEqual(first["volume"], 3.0)
        self.assertEqual(bars.index[0], pd.Timestamp("2025-12-03T10:00Z"))

    def test_align_drop_and_ffill(self):
        idx = pd.date_range("2025-12-03T10:00Z", periods=5, freq="1min")
        a = pd.Series([1, 2, 3, 4, 5], index=idx, name="A", dtype=float)
        b = pd.Series([10, 20, 40], index=idx[[0, 1, 3]], name="B", dtype=float)
        out, _ = align.align([a, b], "drop", 5)
        self.assertEqual(list(out.index), list(idx[[0, 1, 3]]))
        out, _ = align.align([a, b], "ffill", 1)
        self.assertEqual(len(out), 5)
        self.assertEqual(out["B"].tolist(), [10, 20, 20, 40, 40])
        self.assertEqual(out["B_filled"].tolist(), [False, False, True, False, True])
        self.assertFalse(out["A_filled"].any())


class EndToEnd(unittest.TestCase):
    def test_download_and_align(self):
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeFeed)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}/datafeed"
        FakeFeed.flaky_once = {"/datafeed/EURUSD/2025/11/03/10h_ticks.bi5"}
        FakeFeed.missing = {("USDIDXUSD", dt.datetime(2025, 12, 3, 11))}
        FakeFeed.requests = []
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                cmd = [sys.executable, str(HERE / "download.py"), "--base-url", base,
                       "--out", str(tmp / "data"), "--cache", str(tmp / "cache"),
                       "-m", "2025-12", "-i", "EURUSD", "-i", "USDIDXUSD"]
                r = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
                self.assertNotIn("WARN", r.stderr)
                n_first = len(FakeFeed.requests)
                self.assertTrue(all("/2025/11/" in p for p in FakeFeed.requests))
                self.assertIn("/datafeed/EURUSD/2025/11/03/10h_ticks.bi5",
                              [p for p in FakeFeed.requests if FakeFeed.requests.count(p) == 2])

                eur = pd.read_csv(tmp / "data" / "EURUSD_2025-12_1m.csv")
                self.assertEqual(list(eur.columns),
                                 ["timestamp_utc", "open", "high", "low", "close", "volume", "ticks"])
                self.assertEqual(eur["timestamp_utc"].iloc[0], "2025-12-01T00:00:00Z")
                ts = pd.to_datetime(eur["timestamp_utc"], utc=True)
                self.assertFalse((ts.dt.weekday == 5).any())
                self.assertEqual(len(eur), len(download.month_hours("2025-12")) * 60)

                # Re-run with --force: everything comes from cache, no new requests.
                r = subprocess.run(cmd + ["--force"], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(len(FakeFeed.requests), n_first)

                dxy = pd.read_csv(tmp / "data" / "USDIDXUSD_2025-12_1m.csv")
                self.assertEqual(len(dxy), len(eur) - 60)  # the 404 hour
                self.assertTrue(dxy["close"].between(99, 100).all())

                r = subprocess.run([sys.executable, str(HERE / "align.py"), "--data", str(tmp / "data"),
                                    "-i", "EURUSD", "-i", "USDIDXUSD"], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                aligned = pd.read_csv(tmp / "data" / "aligned_EURUSD_USDIDXUSD_1m_drop.csv")
                self.assertEqual(len(aligned), len(dxy))
                self.assertNotIn("2025-12-03T11:30:00Z", set(aligned["timestamp_utc"]))
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
