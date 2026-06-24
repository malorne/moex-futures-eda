#!/usr/bin/env python3
"""Aggregate raw MOEX futures trades to daily contract-level rows.

The raw files are too large to load at once, so this script streams them in
chunks. While reading, it collects quality checks and builds one daily OHLCV row
per contract.

Usage:
    python aggregate_fut_deal.py <csv_path> --month 202501 \
        --out-dir data/processed --chunksize 3000000
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pandas as pd

RAW_DTYPES = {
    "#SYMBOL": "string",
    "SYSTEM": "string",
    "MOMENT": "int64",
    "ID_DEAL": "int64",
    "PRICE_DEAL": "float64",
    "VOLUME": "int64",
    "OPEN_POS": "int64",
    "DIRECTION": "string",
}

# Keep the output columns stable for the notebook, app and exported reports.
DAILY_COLUMNS = [
    "date", "symbol",
    "open_price", "high_price", "low_price", "close_price", "avg_price",
    "total_volume", "num_trades",
    "mean_open_pos", "max_open_pos",
    "buy_volume", "sell_volume", "buy_count", "sell_count",
]


def _new_quality():
    return {
        "rows": 0,
        "nan": pd.Series(dtype="int64"),
        "moment_min": None,
        "moment_max": None,
        "price_min": None, "price_max": None, "price_le0": 0,
        "vol_min": None, "vol_max": None, "vol_le0": 0,
        "op_min": None, "op_max": None, "op_lt0": 0,
        "direction": set(),
        "system": set(),
        "id_arrays": [],
    }


def _upd_min(cur, val):
    return val if cur is None else min(cur, val)


def _upd_max(cur, val):
    return val if cur is None else max(cur, val)


def _process_chunk(chunk: pd.DataFrame, q: dict, parts: list) -> None:
    # MOMENT is YYYYMMDDHHMMSSmmm; dropping the last 9 digits leaves YYYYMMDD.
    moment = chunk["MOMENT"].to_numpy()
    chunk["date_int"] = (moment // 1_000_000_000).astype("int32")

    # Collect quality checks while the chunk is already in memory.
    q["rows"] += len(chunk)
    q["nan"] = q["nan"].add(chunk.isna().sum(), fill_value=0)
    q["moment_min"] = _upd_min(q["moment_min"], int(moment.min()))
    q["moment_max"] = _upd_max(q["moment_max"], int(moment.max()))

    price = chunk["PRICE_DEAL"].to_numpy()
    vol = chunk["VOLUME"].to_numpy()
    op = chunk["OPEN_POS"].to_numpy()
    q["price_min"] = _upd_min(q["price_min"], float(price.min()))
    q["price_max"] = _upd_max(q["price_max"], float(price.max()))
    q["price_le0"] += int((price <= 0).sum())
    q["vol_min"] = _upd_min(q["vol_min"], int(vol.min()))
    q["vol_max"] = _upd_max(q["vol_max"], int(vol.max()))
    q["vol_le0"] += int((vol <= 0).sum())
    q["op_min"] = _upd_min(q["op_min"], int(op.min()))
    q["op_max"] = _upd_max(q["op_max"], int(op.max()))
    q["op_lt0"] += int((op < 0).sum())
    q["direction"].update(chunk["DIRECTION"].dropna().unique().tolist())
    q["system"].update(chunk["SYSTEM"].dropna().unique().tolist())
    q["id_arrays"].append(chunk["ID_DEAL"].to_numpy())

    is_b = (chunk["DIRECTION"] == "B")
    is_s = (chunk["DIRECTION"] == "S")
    chunk["_buy_vol"] = chunk["VOLUME"].where(is_b, 0)
    chunk["_sell_vol"] = chunk["VOLUME"].where(is_s, 0)
    chunk["_buy_cnt"] = is_b.astype("int8")
    chunk["_sell_cnt"] = is_s.astype("int8")

    # Stable sorting keeps the first and last trade correct inside each chunk.
    chunk = chunk.sort_values("MOMENT", kind="stable")
    part = chunk.groupby(["#SYMBOL", "date_int"], observed=True).agg(
        open_price=("PRICE_DEAL", "first"),
        close_price=("PRICE_DEAL", "last"),
        high_price=("PRICE_DEAL", "max"),
        low_price=("PRICE_DEAL", "min"),
        sum_price=("PRICE_DEAL", "sum"),
        num_trades=("PRICE_DEAL", "size"),
        total_volume=("VOLUME", "sum"),
        sum_open_pos=("OPEN_POS", "sum"),
        max_open_pos=("OPEN_POS", "max"),
        first_moment=("MOMENT", "first"),
        last_moment=("MOMENT", "last"),
        buy_volume=("_buy_vol", "sum"),
        sell_volume=("_sell_vol", "sum"),
        buy_count=("_buy_cnt", "sum"),
        sell_count=("_sell_cnt", "sum"),
    ).reset_index()
    parts.append(part)


def _combine(parts: list) -> pd.DataFrame:
    allp = pd.concat(parts, ignore_index=True)
    keys = ["#SYMBOL", "date_int"]

    agg = allp.groupby(keys, observed=True).agg(
        high_price=("high_price", "max"),
        low_price=("low_price", "min"),
        sum_price=("sum_price", "sum"),
        num_trades=("num_trades", "sum"),
        total_volume=("total_volume", "sum"),
        sum_open_pos=("sum_open_pos", "sum"),
        max_open_pos=("max_open_pos", "max"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        buy_count=("buy_count", "sum"),
        sell_count=("sell_count", "sum"),
    )
    # Open/close must be chosen after all chunks are combined.
    open_df = (allp.sort_values("first_moment", kind="stable")
               .groupby(keys, observed=True)
               .agg(open_price=("open_price", "first")))
    close_df = (allp.sort_values("last_moment", kind="stable")
                .groupby(keys, observed=True)
                .agg(close_price=("close_price", "last")))

    daily = agg.join(open_df).join(close_df).reset_index()
    daily["avg_price"] = daily["sum_price"] / daily["num_trades"]
    daily["mean_open_pos"] = daily["sum_open_pos"] / daily["num_trades"]
    daily["date"] = pd.to_datetime(daily["date_int"].astype(str), format="%Y%m%d")
    daily["symbol"] = daily["#SYMBOL"].astype("string")
    daily = daily[DAILY_COLUMNS].sort_values(["symbol", "date"]).reset_index(drop=True)
    return daily


def aggregate_csv(csv_path: str, chunksize: int = 3_000_000, log=print):
    q = _new_quality()
    parts: list = []
    t0 = time.time()
    n_chunks = 0
    reader = pd.read_csv(csv_path, dtype=RAW_DTYPES, chunksize=chunksize)
    for chunk in reader:
        _process_chunk(chunk, q, parts)
        n_chunks += 1
        log(f"  chunk {n_chunks}: rows so far={q['rows']:,} "
            f"({time.time() - t0:.1f}s)")

    daily = _combine(parts)

    ids = np.concatenate(q["id_arrays"]) if q["id_arrays"] else np.array([], dtype="int64")
    n_unique_ids = int(np.unique(ids).size)
    quality = {
        "rows": int(q["rows"]),
        "n_chunks": n_chunks,
        "nan_by_column": {k: int(v) for k, v in q["nan"].items()},
        "moment_min": int(q["moment_min"]),
        "moment_max": int(q["moment_max"]),
        "datetime_min": str(pd.to_datetime(str(q["moment_min"]), format="%Y%m%d%H%M%S%f")),
        "datetime_max": str(pd.to_datetime(str(q["moment_max"]), format="%Y%m%d%H%M%S%f")),
        "price_min": q["price_min"], "price_max": q["price_max"],
        "price_le0": int(q["price_le0"]),
        "volume_min": q["vol_min"], "volume_max": q["vol_max"],
        "volume_le0": int(q["vol_le0"]),
        "open_pos_min": q["op_min"], "open_pos_max": q["op_max"],
        "open_pos_lt0": int(q["op_lt0"]),
        "direction_values": sorted(q["direction"]),
        "system_values": sorted(q["system"]),
        "n_unique_symbols": int(daily["symbol"].nunique()),
        "n_id_deal_total": int(ids.size),
        "n_id_deal_unique": n_unique_ids,
        "n_id_deal_duplicates": int(ids.size - n_unique_ids),
        "elapsed_sec": round(time.time() - t0, 1),
    }
    return daily, quality


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--month", required=True, help="tag like 202501")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--chunksize", type=int, default=3_000_000)
    a = ap.parse_args()

    os.makedirs(a.out_dir, exist_ok=True)
    daily, quality = aggregate_csv(a.csv_path, chunksize=a.chunksize)

    pq = os.path.join(a.out_dir, f"daily_{a.month}.parquet")
    daily.to_parquet(pq, index=False)
    qj = os.path.join(a.out_dir, f"quality_{a.month}.json")
    with open(qj, "w") as f:
        json.dump(quality, f, ensure_ascii=False, indent=2)

    print("\n=== QUALITY ===")
    print(json.dumps(quality, ensure_ascii=False, indent=2))
    print(f"\n=== DAILY shape: {daily.shape} -> {pq}")
    print(daily.head(8).to_string())


if __name__ == "__main__":
    main()
