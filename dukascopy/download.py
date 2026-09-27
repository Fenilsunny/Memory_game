#!/usr/bin/env python3
"""Download Dukascopy tick data and aggregate it into 1-minute OHLCV bars.

Source: https://datafeed.dukascopy.com/datafeed/{INSTRUMENT}/{YYYY}/{MM}/{DD}/{HH}h_ticks.bi5
Each file holds one hour of ticks, LZMA-compressed. Each record is 20 bytes,
big-endian ``>3i2f``: ms offset from the start of the hour, ask, bid,
ask volume, bid volume. Prices are integers that you divide by the
instrument's point factor.

NOTE: the MM path segment is ZERO-BASED (January = 00, December = 11).

Output: one CSV per instrument per month, e.g. ``data/EURUSD_2025-12_1m.csv``.

Usage:
    python download.py --check                     # confirm each symbol returns data
    python download.py                             # full default job (Dec 2025 - Mar 2026)
    python download.py -i EURUSD -m 2026-01        # just one instrument/month
    python download.py --dxy-stooq                 # daily DXY fallback from Stooq
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import lzma
import random
import struct
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

BASE_URL = "https://datafeed.dukascopy.com/datafeed"
STOOQ_DXY_URL = "https://stooq.com/q/d/l/?s=dx.f&i=d"

# Point factor = divisor that turns the raw integer price into a real price.
# (lo, hi) is a rough plausible price range, used to catch a wrong factor.
INSTRUMENTS = {
    "EURUSD": {"point": 1e5, "range": (0.8, 1.6)},
    "GBPUSD": {"point": 1e5, "range": (1.0, 1.8)},
    "USDIDXUSD": {"point": 1e3, "range": (80.0, 130.0)},
}
DEFAULT_MONTHS = ["2025-12", "2026-01", "2026-02", "2026-03"]

RECORD = struct.Struct(">3i2f")  # 20 bytes
RECORD_DTYPE = np.dtype([("ms", ">i4"), ("ask", ">i4"), ("bid", ">i4"),
                         ("ask_volume", ">f4"), ("bid_volume", ">f4")])
HERE = Path(__file__).resolve().parent


def hour_url(base_url: str, instrument: str, hour: dt.datetime) -> str:
    # Zero-based month: the most common mistake with this feed.
    return (
        f"{base_url}/{instrument}/{hour.year:04d}/{hour.month - 1:02d}/"
        f"{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"
    )


def is_market_closed(hour: dt.datetime) -> bool:
    """True for hours with no FX trading. Conservative: in winter the market
    reopens Sunday 22:00 UTC, in summer 21:00 UTC, so we still fetch Sunday
    21:00 (it's just empty in winter). Friday close is 22:00 UTC in winter
    and 21:00 UTC in summer, so Friday 21:00 is always fetched."""
    wd = hour.weekday()  # Mon=0 ... Sun=6
    if wd == 5:
        return True
    if wd == 4 and hour.hour >= 22:
        return True
    if wd == 6 and hour.hour < 21:
        return True
    return False


def month_hours(month: str) -> list[dt.datetime]:
    start = dt.datetime.strptime(month, "%Y-%m")
    end = (start + dt.timedelta(days=32)).replace(day=1)
    hours = []
    h = start
    while h < end:
        if not is_market_closed(h):
            hours.append(h)
        h += dt.timedelta(hours=1)
    return hours


class Fetcher:
    def __init__(self, base_url: str, cache_dir: Path, retries: int = 5, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.cache_dir = cache_dir
        self.retries = retries
        self.timeout = timeout

    def cache_path(self, instrument: str, hour: dt.datetime) -> Path:
        # Cache uses calendar months (01-12) so it's readable; only the URL is zero-based.
        return self.cache_dir / instrument / hour.strftime("%Y/%m/%d") / f"{hour.hour:02d}h_ticks.bi5"

    def get(self, instrument: str, hour: dt.datetime) -> bytes:
        """Return the raw .bi5 bytes for an hour (b"" if there's no data).
        A 404 is cached as an empty file so re-runs don't refetch it."""
        path = self.cache_path(instrument, hour)
        if path.exists():
            return path.read_bytes()

        url = hour_url(self.base_url, instrument, hour)
        delay = 1.0
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    data = b""
                    break
                err = f"HTTP {e.code}"
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                err = str(e)
            if attempt == self.retries:
                raise RuntimeError(f"{url}: failed after {attempt} attempts ({err})")
            time.sleep(delay + random.uniform(0, delay / 2))
            delay *= 2

        # Only cache payloads that decompress, so a truncated download is refetched.
        if data:
            decode_bi5(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return data


def decode_bi5(data: bytes) -> np.ndarray:
    """Decompress one .bi5 payload into a structured array of raw records."""
    if not data:
        return np.empty(0, dtype=RECORD_DTYPE)
    raw = lzma.decompress(data)
    if len(raw) % RECORD.size:
        raise ValueError(f"corrupt bi5: {len(raw)} bytes is not a multiple of {RECORD.size}")
    return np.frombuffer(raw, dtype=RECORD_DTYPE)


def ticks_for_hour(data: bytes, hour: dt.datetime, point: float) -> pd.DataFrame:
    rec = decode_bi5(data)
    ts = pd.Timestamp(hour, tz="UTC") + pd.to_timedelta(rec["ms"].astype("int64"), unit="ms")
    return pd.DataFrame(
        {
            "ask": rec["ask"] / point,
            "bid": rec["bid"] / point,
            "ask_volume": rec["ask_volume"].astype(float),
            "bid_volume": rec["bid_volume"].astype(float),
        },
        index=pd.DatetimeIndex(ts, name="timestamp_utc"),
    )


def to_1m_bars(ticks: pd.DataFrame, side: str) -> pd.DataFrame:
    """Aggregate ticks into 1-minute OHLCV bars. Minutes with no ticks are
    left out, not filled: gap handling belongs in the alignment step."""
    if side == "mid":
        price = (ticks["bid"] + ticks["ask"]) / 2
        volume = ticks["bid_volume"] + ticks["ask_volume"]
    else:
        price = ticks[side]
        volume = ticks[f"{side}_volume"]
    g = pd.DataFrame({"p": price, "v": volume}).resample("1min", label="left", closed="left")
    bars = g["p"].ohlc()
    bars["volume"] = g["v"].sum()
    bars["ticks"] = g["p"].count()
    return bars[bars["ticks"] > 0]


def download_month(fetcher: Fetcher, instrument: str, month: str, side: str,
                   workers: int, out_dir: Path, force: bool = False) -> Path:
    out = out_dir / f"{instrument}_{month}_1m.csv"
    if out.exists() and not force:
        print(f"[skip] {out.name} exists (use --force to rebuild)")
        return out

    point = INSTRUMENTS[instrument]["point"]
    hours = month_hours(month)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        payloads = list(pool.map(lambda h: fetcher.get(instrument, h), hours))

    frames = [ticks_for_hour(d, h, point) for h, d in zip(hours, payloads) if d]
    if not frames:
        raise RuntimeError(f"{instrument} {month}: no data in any of {len(hours)} hourly files")
    bars = to_1m_bars(pd.concat(frames).sort_index(), side)

    lo, hi = INSTRUMENTS[instrument]["range"]
    med = bars["close"].median()
    if not lo <= med <= hi:
        print(f"[WARN] {instrument} {month}: median close {med:.5f} is outside "
              f"{lo}-{hi}; the point factor may be wrong", file=sys.stderr)

    out_dir.mkdir(parents=True, exist_ok=True)
    bars.index = bars.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    bars.index.name = "timestamp_utc"
    bars.to_csv(out, float_format="%.6f")
    empty = sum(1 for d in payloads if not d)
    print(f"[done] {out.name}: {len(bars):,} bars from {len(hours)} hours "
          f"({empty} empty) in {time.time() - t0:.0f}s")
    return out


def check_symbols(fetcher: Fetcher, instruments: list[str]) -> bool:
    """Fetch a few known weekday hours per instrument and report prices."""
    probe = [dt.datetime(2025, 12, 3, h) for h in (10, 14)] + [dt.datetime(2026, 1, 14, 14)]
    ok = True
    for inst in instruments:
        point = INSTRUMENTS[inst]["point"]
        try:
            ticks = pd.concat([ticks_for_hour(fetcher.get(inst, h), h, point) for h in probe])
        except Exception as e:  # noqa: BLE001 - report every failure mode here
            print(f"[FAIL] {inst}: {e}")
            ok = False
            continue
        if ticks.empty:
            print(f"[FAIL] {inst}: probe hours returned no ticks")
            ok = False
            continue
        lo, hi = INSTRUMENTS[inst]["range"]
        mid = ((ticks["bid"] + ticks["ask"]) / 2).median()
        flag = "OK" if lo <= mid <= hi else "WARN point factor?"
        print(f"[{flag}] {inst}: {len(ticks):,} ticks, median mid {mid:.5f} "
              f"(first {ticks.index[0].isoformat()})")
        ok &= flag == "OK"
    return ok


def download_stooq_dxy(out_dir: Path, start: str, end: str) -> Path:
    """Daily DXY fallback from Stooq for when USDIDXUSD isn't available."""
    req = urllib.request.Request(STOOQ_DXY_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        df = pd.read_csv(io.BytesIO(resp.read()), parse_dates=["Date"])
    df = df[(df["Date"] >= start) & (df["Date"] <= end)]
    df = df.rename(columns=str.lower).rename(columns={"date": "date_utc"})
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"DXY_stooq_{start[:7]}_{end[:7]}_1d.csv"
    df.to_csv(out, index=False, date_format="%Y-%m-%d")
    print(f"[done] {out.name}: {len(df)} daily bars")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--instrument", action="append", choices=INSTRUMENTS,
                    help="repeatable; default: all")
    ap.add_argument("-m", "--month", action="append", help="YYYY-MM, repeatable; default: 2025-12..2026-03")
    ap.add_argument("--side", choices=["bid", "ask", "mid"], default="bid", help="price side for bars")
    ap.add_argument("--workers", type=int, default=4, help="concurrent downloads (keep this small)")
    ap.add_argument("--retries", type=int, default=5)
    ap.add_argument("--out", type=Path, default=HERE / "data")
    ap.add_argument("--cache", type=Path, default=HERE / "cache")
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--force", action="store_true", help="rebuild CSVs that already exist")
    ap.add_argument("--check", action="store_true", help="only verify each symbol returns data")
    ap.add_argument("--dxy-stooq", action="store_true", help="download daily DXY from Stooq instead")
    args = ap.parse_args()

    instruments = args.instrument or list(INSTRUMENTS)
    months = args.month or DEFAULT_MONTHS
    fetcher = Fetcher(args.base_url, args.cache, retries=args.retries)

    if args.dxy_stooq:
        first = months[0] + "-01"
        last = (pd.Timestamp(months[-1] + "-01") + pd.offsets.MonthEnd(0)).strftime("%Y-%m-%d")
        download_stooq_dxy(args.out, first, last)
        return 0
    if args.check:
        return 0 if check_symbols(fetcher, instruments) else 1

    failed = []
    for inst in instruments:
        for month in months:
            try:
                download_month(fetcher, inst, month, args.side, args.workers, args.out, args.force)
            except Exception as e:  # noqa: BLE001 - keep going, retry failed months later
                print(f"[FAIL] {inst} {month}: {e}", file=sys.stderr)
                failed.append(f"-i {inst} -m {month}")
    if failed:
        print("\nFailed batches (re-run to retry; cached hours are not refetched):", file=sys.stderr)
        for f in failed:
            print(f"  python download.py {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
