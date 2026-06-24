#!/usr/bin/env python3
"""Build the daily dataset from the monthly MOEX futures archives.

For each month we download the archive if needed, extract the CSV, run the
chunked aggregation and save both the daily table and the quality report. Months
that are already processed are skipped.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import py7zr  # noqa: E402
import yadisk  # noqa: E402
import aggregate_fut_deal as agg  # noqa: E402

ROOT = os.environ.get("MOEX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PUBLIC = "https://disk.360.yandex.ru/d/xv-QHgR9iPxyWg"
PREFIX = "/FUT, OPT_Срочный рынок (01.2025-12.2025)/"
RAW = os.path.join(ROOT, "data/raw")
INTERIM = os.path.join(ROOT, "data/interim")
PROC = os.path.join(ROOT, "data/processed")

MONTHS = [f"2025{mm:02d}" for mm in range(1, 13)]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def dl_with_retry(rel_path, out, attempts=6, timeout=120):
    last = None
    for i in range(1, attempts + 1):
        try:
            yadisk.download(PUBLIC, rel_path, out, timeout=timeout)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            log(f"    download attempt {i}/{attempts} failed: {e!r}")
            if os.path.exists(out):
                try:
                    os.remove(out)
                except OSError:
                    pass
    raise last


def extract(sevenz, dst):
    with py7zr.SevenZipFile(sevenz, "r") as z:
        names = z.getnames()
        z.extractall(path=dst)
    return os.path.join(dst, names[0])


def main():
    for d in (RAW, INTERIM, PROC):
        os.makedirs(d, exist_ok=True)

    for m in MONTHS:
        pq = os.path.join(PROC, f"daily_{m}.parquet")
        if os.path.exists(pq):
            log(f"[{m}] daily parquet exists -> skip")
            continue

        log(f"[{m}] === START ===")
        sevenz = os.path.join(RAW, f"{m}_fut_deal.7z")
        if not os.path.exists(sevenz):
            log(f"[{m}] downloading...")
            dl_with_retry(f"{PREFIX}{m}_fut_deal.7z", sevenz)
        log(f"[{m}] extracting...")
        csv = extract(sevenz, INTERIM)

        log(f"[{m}] aggregating...")
        daily, quality = agg.aggregate_csv(csv, chunksize=3_000_000,
                                           log=lambda *a, **k: None)
        daily.to_parquet(pq, index=False)
        with open(os.path.join(PROC, f"quality_{m}.json"), "w") as f:
            json.dump(quality, f, ensure_ascii=False, indent=2)
        log(f"[{m}] daily{daily.shape} rows={quality['rows']:,} "
            f"range {quality['datetime_min']}..{quality['datetime_max']} "
            f"symbols={quality['n_unique_symbols']} "
            f"dups={quality['n_id_deal_duplicates']}")

        try:
            os.remove(csv)  # The extracted CSV is large; keep only the compact output.
        except OSError:
            pass
        log(f"[{m}] removed extracted CSV. === DONE ===")

    log("ALL MONTHS DONE")


if __name__ == "__main__":
    main()
