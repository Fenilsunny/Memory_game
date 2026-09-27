# Dukascopy 1-minute bars: EUR/USD, GBP/USD, DXY

These scripts download Dukascopy's free tick feed and aggregate it into 1-minute OHLCV CSVs, one per instrument per month. `align.py` then puts the instruments on a common UTC index.

```bash
pip install -r requirements.txt

python download.py --check     # 1. confirm each symbol (esp. USDIDXUSD) returns sane prices
python download.py             # 2. EURUSD, GBPUSD, USDIDXUSD for 2025-12 .. 2026-03
python align.py                # 3. outer-join onto one 1-min UTC index, drop gaps explicitly
```

## Output

`data/EURUSD_2025-12_1m.csv`, etc.:

```
timestamp_utc,open,high,low,close,volume,ticks
2025-12-01T00:00:00Z,1.159820,1.159900,1.159780,1.159860,12.340000,57
```

- `timestamp_utc` is the bar's **open** time in UTC (ISO 8601, `Z` suffix). A bar covers `[t, t+1min)`.
- Prices are **bid** by default. Use `--side ask` or `--side mid` for the others. `volume` is Dukascopy's tick volume for that side (both sides summed for mid).
- Minutes with no ticks produce no row. Nothing is filled at this stage.

## How it works

- Fetches `https://datafeed.dukascopy.com/datafeed/{INST}/{YYYY}/{MM}/{DD}/{HH}h_ticks.bi5`, where **MM is zero-based** (Dec = `11`). This is covered by a unit test and by the mock-feed end-to-end test.
- Decompresses with LZMA and decodes big-endian `>3i2f` records (ms offset, ask, bid, ask vol, bid vol). Prices are divided by the point factor: 1e5 for the FX pairs, 1e3 for USDIDXUSD. The script warns if the median price is outside a plausible range, which usually means a wrong factor.
- Skips closed hours: all of Saturday, Friday from 22:00 UTC, and Sunday before 21:00 UTC.
- Downloads with 4 concurrent connections (`--workers`) and retries 5 times with exponential backoff plus jitter. A 404 counts as an empty hour.
- Caches every hour under `cache/` (404s are stored as empty files), so a re-run doesn't refetch anything. Existing monthly CSVs are skipped unless you pass `--force`.
- A failed month doesn't stop the job. The script prints the exact command to retry it at the end.

## DXY

`USDIDXUSD` is Dukascopy's dollar-index CFD. Run `--check` first. If it fails, fall back to daily DXY from Stooq:

```bash
python download.py --dxy-stooq   # -> data/DXY_stooq_2025-12_2026-03_1d.csv
```

## Alignment

```bash
python align.py                              # --gaps drop: keep only minutes where all instruments traded
python align.py --gaps ffill --ffill-limit 5 # carry values forward up to 5 min, with {INST}_filled flag columns
python align.py -i EURUSD -i GBPUSD          # just the pair
```

Both modes print a per-instrument gap report (real bars, minutes missing from the union, values filled, rows dropped), so misalignment shows up in the output.

## Tests

```bash
python -m unittest test_download -v   # offline; runs against a local mock of the feed
```
