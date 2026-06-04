#!/usr/bin/env python3
"""Combine monthly daily files, build the per-symbol summary, select the
analysis instruments (perpetual '...F' futures) and engineer features.

Outputs (in data/processed):
  daily_year_2025.parquet    all symbols, all days (one row per symbol-day)
  symbol_summary.parquet/.csv per-#SYMBOL liquidity/quality metrics
  analysis_2025.parquet      selected instruments + engineered features
"""
from __future__ import annotations

import glob
import os

import numpy as np
import pandas as pd

ROOT = os.environ.get("MOEX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data/processed")

# Analysis set: liquid perpetual ("evergreen", ticker ends in 'F') futures.
# Asset-class labels follow MOEX ticker naming; confirm base asset via the
# official MOEX instrument reference before quoting them as fact.
PERPETUALS = {
    "IMOEXF":  "Index (MOEX Index)",
    "USDRUBF": "Currency (USD/RUB)",
    "CNYRUBF": "Currency (CNY/RUB)",
    "EURRUBF": "Currency (EUR/RUB)",
    "GLDRUBF": "Metal (Gold/RUB)",
    "SBERF":   "Equity (Sberbank)",
    "GAZPF":   "Equity (Gazprom)",
}


def load_all_daily() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(PROC, "daily_2025[0-1][0-9].parquet")))
    if not files:
        raise SystemExit("No monthly daily_YYYYMM.parquet files found yet.")
    df = pd.concat((pd.read_parquet(f) for f in files), ignore_index=True)
    df["symbol"] = df["symbol"].astype("string")
    df["date"] = pd.to_datetime(df["date"])
    # If a symbol-day appears in two files (month boundary), merge it safely.
    df = _merge_boundary_dupes(df)
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df, files


def _merge_boundary_dupes(df: pd.DataFrame) -> pd.DataFrame:
    """A (symbol, date) can appear in two monthly files (the evening session of
    a month's last day lands in the next month's file). Merge such rows: open =
    earliest file's open, close = latest file's close, sums add, means are
    trade-weighted. Files are concatenated in chronological order, so 'first'/
    'last' correctly map to earliest/latest session."""
    dup = df.duplicated(["symbol", "date"], keep=False)
    if not dup.any():
        return df
    clean = df[~dup]
    d = df[dup].copy()
    d["_p"] = d["avg_price"] * d["num_trades"]
    d["_o"] = d["mean_open_pos"] * d["num_trades"]
    merged = d.groupby(["symbol", "date"], observed=True).agg(
        open_price=("open_price", "first"),
        high_price=("high_price", "max"),
        low_price=("low_price", "min"),
        close_price=("close_price", "last"),
        total_volume=("total_volume", "sum"),
        num_trades=("num_trades", "sum"),
        max_open_pos=("max_open_pos", "max"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        buy_count=("buy_count", "sum"),
        sell_count=("sell_count", "sum"),
        _p=("_p", "sum"),
        _o=("_o", "sum"),
    ).reset_index()
    merged["avg_price"] = merged["_p"] / merged["num_trades"]
    merged["mean_open_pos"] = merged["_o"] / merged["num_trades"]
    merged = merged.drop(columns=["_p", "_o"])
    return pd.concat([clean, merged], ignore_index=True)


def symbol_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("symbol", observed=True)
    s = g.agg(
        num_deals=("num_trades", "sum"),
        total_volume=("total_volume", "sum"),
        min_price=("low_price", "min"),
        max_price=("high_price", "max"),
        mean_open_pos=("mean_open_pos", "mean"),
        max_open_pos=("max_open_pos", "max"),
        buy_count=("buy_count", "sum"),
        sell_count=("sell_count", "sum"),
        buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"),
        num_trading_days=("date", "nunique"),
        std_close_price=("close_price", "std"),
    )
    # trade-weighted mean price (exact trade-level mean recovered from daily)
    wp = df.assign(_p=df["avg_price"] * df["num_trades"])
    s["mean_price"] = (wp.groupby("symbol", observed=True)["_p"].sum()
                       / s["num_deals"])
    s["mean_volume"] = s["total_volume"] / s["num_deals"]
    tot_dir = (s["buy_count"] + s["sell_count"]).replace(0, np.nan)
    s["buy_share_cnt"] = s["buy_count"] / tot_dir
    tot_vol = (s["buy_volume"] + s["sell_volume"]).replace(0, np.nan)
    s["buy_share_vol"] = s["buy_volume"] / tot_vol
    s["has_direction"] = tot_dir.notna()
    s = s.sort_values("num_deals", ascending=False)
    return s


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["symbol", "date"]).copy()
    g = df.groupby("symbol", observed=True)
    df["daily_return"] = g["close_price"].pct_change(fill_method=None) * 100.0
    df["abs_return"] = df["daily_return"].abs()
    df["price_range"] = df["high_price"] - df["low_price"]
    df["relative_range"] = df["price_range"] / df["close_price"] * 100.0
    df["volume_per_trade"] = df["total_volume"] / df["num_trades"]
    tot = (df["buy_volume"] + df["sell_volume"]).replace(0, np.nan)
    df["buy_share"] = df["buy_volume"] / tot
    df["direction_imbalance"] = (df["buy_share"] - 0.5).abs()
    first_close = g["close_price"].transform("first")
    df["normalized_close"] = df["close_price"] / first_close * 100.0
    # calendar features (intraday hour/minute are not available post-aggregation)
    df["month"] = df["date"].dt.month
    df["weekday"] = df["date"].dt.weekday
    df["weekday_name"] = df["date"].dt.day_name()
    return df


def main():
    df, files = load_all_daily()
    print(f"Loaded {len(files)} monthly files -> daily rows={len(df):,}, "
          f"symbols={df['symbol'].nunique()}, "
          f"dates {df['date'].min().date()}..{df['date'].max().date()}")

    df.to_parquet(os.path.join(PROC, "daily_year_2025.parquet"), index=False)

    summ = symbol_summary(df)
    summ.to_parquet(os.path.join(PROC, "symbol_summary.parquet"))
    summ.reset_index().to_csv(os.path.join(PROC, "symbol_summary.csv"), index=False)

    print("\n=== TOP-15 symbols by number of deals ===")
    cols = ["num_deals", "total_volume", "mean_volume", "mean_price",
            "std_close_price", "mean_open_pos", "num_trading_days",
            "buy_share_cnt", "has_direction"]
    print(summ[cols].head(15).to_string())

    # selected analysis set
    sel = df[df["symbol"].isin(PERPETUALS)].copy()
    sel["asset_class"] = sel["symbol"].map(PERPETUALS).astype("string")
    sel = add_features(sel)
    sel.to_parquet(os.path.join(PROC, "analysis_2025.parquet"), index=False)

    print("\n=== analysis_2025 (selected perpetuals) ===")
    print(f"rows={len(sel):,}, symbols={sel['symbol'].nunique()}, "
          f"dates {sel['date'].min().date()}..{sel['date'].max().date()}")
    print(sel.groupby("symbol", observed=True).agg(
        days=("date", "nunique"),
        mean_close=("close_price", "mean"),
        vol_of_return=("daily_return", "std"),
        mean_rel_range=("relative_range", "mean"),
        mean_buy_share=("buy_share", "mean"),
    ).to_string())


if __name__ == "__main__":
    main()
