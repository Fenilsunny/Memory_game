#!/usr/bin/env python3
"""Align the monthly 1-minute CSVs of several instruments onto one UTC index.

The instruments are outer-joined on a 1-minute UTC index. Gaps are then
handled EXPLICITLY using one of these modes:

  --gaps drop   (default) keep only minutes where every instrument has a real bar.
                Safest for correlation work: nothing is invented.
  --gaps ffill  forward-fill each instrument's close by up to --ffill-limit minutes.
                Adds a ``{INST}_filled`` flag column so you can see which values
                were carried forward. Rows that are still missing after the fill
                are dropped.

In both modes a per-instrument gap report is printed, so a misalignment
shows up in the output instead of passing unnoticed.

Usage:
    python align.py                                   # EURUSD, GBPUSD, USDIDXUSD from data/
    python align.py --gaps ffill --ffill-limit 5
    python align.py -i EURUSD -i GBPUSD --out data/eurgbp_aligned.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def load_instrument(data_dir: Path, instrument: str, field: str) -> pd.Series:
    files = sorted(data_dir.glob(f"{instrument}_*_1m.csv"))
    if not files:
        raise FileNotFoundError(f"no {instrument}_*_1m.csv files in {data_dir}")
    df = pd.concat(pd.read_csv(f, index_col="timestamp_utc") for f in files)
    df.index = pd.to_datetime(df.index, utc=True, format="%Y-%m-%dT%H:%M:%SZ")
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df[field].rename(instrument)


def align(series: list[pd.Series], gaps: str, ffill_limit: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    wide = pd.concat(series, axis=1, join="outer").sort_index()
    names = [s.name for s in series]

    report = pd.DataFrame({
        "real_bars": wide.notna().sum(),
        "missing_in_union": wide.isna().sum(),
    })

    if gaps == "drop":
        out = wide.dropna(how="any")
        report["filled"] = 0
    else:
        filled = wide.ffill(limit=ffill_limit)
        for n in names:
            wide[f"{n}_filled"] = wide[n].isna() & filled[n].notna()
        wide[names] = filled[names]
        out = wide.dropna(subset=names, how="any")
        report["filled"] = [int(out[f"{n}_filled"].sum()) for n in names]

    report.loc["__rows__"] = [len(wide), len(wide) - len(out), 0]
    report = report.rename(index={"__rows__": "(union rows / dropped)"})
    return out, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--instrument", action="append",
                    help="repeatable; default: EURUSD GBPUSD USDIDXUSD")
    ap.add_argument("--data", type=Path, default=HERE / "data")
    ap.add_argument("--field", default="close", help="which bar column to align (default: close)")
    ap.add_argument("--gaps", choices=["drop", "ffill"], default="drop")
    ap.add_argument("--ffill-limit", type=int, default=5, help="max minutes to carry a value forward")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    instruments = args.instrument or ["EURUSD", "GBPUSD", "USDIDXUSD"]
    series = [load_instrument(args.data, i, args.field) for i in instruments]
    out, report = align(series, args.gaps, args.ffill_limit)

    dest = args.out or args.data / f"aligned_{'_'.join(instruments)}_1m_{args.gaps}.csv"
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.index.name = "timestamp_utc"
    out.to_csv(dest, float_format="%.6f")

    print(report.to_string())
    print(f"\n[done] {dest.name}: {len(out):,} aligned rows (gaps={args.gaps})")
    if len(out) == 0:
        print("[WARN] no overlapping minutes; check the inputs", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
