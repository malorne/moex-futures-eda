#!/usr/bin/env python3
"""Shared analysis functions for the notebook and Streamlit app.

Keeping the calculations here helps the notebook, exported figures and web app
show the same results.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

try:
    from scipy import stats as _sps
    HAVE_SCIPY = True
except Exception:  # noqa: BLE001
    HAVE_SCIPY = False

def _resolve_root() -> str:
    """Find the project root in local, Docker and hosted environments."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    marker = os.path.join("data", "processed", "daily_year_2025.parquet")
    for cand in (os.environ.get("MOEX_ROOT"), here, os.getcwd()):
        if cand and os.path.exists(os.path.join(cand, marker)):
            return cand
    return os.environ.get("MOEX_ROOT") or here


ROOT = _resolve_root()
PROC = os.path.join(ROOT, "data/processed")
INTERIM = os.path.join(ROOT, "data/interim")

# Stable order and colors make plots easier to compare across pages.
SYMBOL_ORDER = ["IMOEXF", "USDRUBF", "CNYRUBF", "EURRUBF",
                "GLDRUBF", "GAZPF", "SBERF"]
ASSET_CLASS = {
    "IMOEXF": "Index", "USDRUBF": "Currency", "CNYRUBF": "Currency",
    "EURRUBF": "Currency", "GLDRUBF": "Metal", "GAZPF": "Equity",
    "SBERF": "Equity",
}
PALETTE = dict(zip(SYMBOL_ORDER, sns.color_palette("tab10", len(SYMBOL_ORDER))))

NUMERIC_FIELDS = [
    "close_price", "total_volume", "num_trades", "mean_open_pos",
    "daily_return", "abs_return", "relative_range", "volume_per_trade",
    "buy_share", "direction_imbalance",
]


# Data loading
def load_analysis() -> pd.DataFrame:
    df = pd.read_parquet(os.path.join(PROC, "analysis_2025.parquet"))
    df["date"] = pd.to_datetime(df["date"])
    df["symbol"] = df["symbol"].astype("string")
    return df


def load_summary() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(PROC, "symbol_summary.parquet"))


def load_daily_all() -> pd.DataFrame:
    df = pd.read_parquet(os.path.join(PROC, "daily_year_2025.parquet"))
    df["date"] = pd.to_datetime(df["date"])
    df["symbol"] = df["symbol"].astype("string")
    return df


def _ordered(df: pd.DataFrame) -> list:
    present = [s for s in SYMBOL_ORDER if s in set(df["symbol"].unique())]
    return present


# Descriptive statistics
def describe_overall(df: pd.DataFrame, fields=None) -> pd.DataFrame:
    fields = fields or NUMERIC_FIELDS
    fields = [f for f in fields if f in df.columns]
    d = df[fields].describe(percentiles=[0.25, 0.5, 0.75]).T
    d["median"] = df[fields].median()
    d = d.rename(columns={"std": "std", "25%": "q25", "50%": "q50", "75%": "q75"})
    return d[["count", "mean", "median", "std", "min", "q25", "q50", "q75", "max"]]


def describe_by_symbol(df: pd.DataFrame, field: str) -> pd.DataFrame:
    g = df.groupby("symbol", observed=True)[field]
    out = pd.DataFrame({
        "mean": g.mean(), "median": g.median(), "std": g.std(),
        "min": g.min(), "max": g.max(),
    })
    return out.reindex(_ordered(df))


# Basic plots
def fig_normalized_close(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for s in _ordered(df):
        d = df[df["symbol"] == s]
        ax.plot(d["date"], d["normalized_close"], label=s, color=PALETTE[s], lw=1.4)
    ax.axhline(100, color="grey", ls="--", lw=.8)
    ax.set_title("Normalized close price (first trading day = 100)")
    ax.set_xlabel("Date"); ax.set_ylabel("Normalized close, %")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    return fig


def fig_return_hist(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 5))
    r = df["daily_return"].dropna()
    ax.hist(r, bins=80, color="#4C72B0", edgecolor="white")
    ax.axvline(r.mean(), color="red", ls="--", lw=1,
               label=f"mean={r.mean():.2f}%")
    ax.axvline(r.median(), color="green", ls="--", lw=1,
               label=f"median={r.median():.2f}%")
    ax.set_title("Distribution of daily returns (all selected instruments)")
    ax.set_xlabel("Daily return, %"); ax.set_ylabel("Count")
    ax.legend()
    fig.tight_layout()
    return fig


def fig_volume_vs_absreturn(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 6))
    for s in _ordered(df):
        d = df[df["symbol"] == s]
        ax.scatter(d["total_volume"], d["abs_return"], s=14, alpha=.5,
                   color=PALETTE[s], label=s)
    ax.set_xscale("log")
    ax.set_title("Daily volume vs absolute daily return")
    ax.set_xlabel("Total daily volume (log scale)")
    ax.set_ylabel("|daily return|, %")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    return fig


def fig_return_box(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 5.5))
    order = _ordered(df)
    sns.boxplot(data=df, x="symbol", y="daily_return", order=order,
                hue="symbol", palette=PALETTE, legend=False, ax=ax, fliersize=2)
    ax.axhline(0, color="grey", ls="--", lw=.8)
    ax.set_title("Daily return distribution by instrument")
    ax.set_xlabel(""); ax.set_ylabel("Daily return, %")
    fig.tight_layout()
    return fig


# Detailed comparisons
def fig_liquidity_bars(df: pd.DataFrame):
    order = _ordered(df)
    g = df.groupby("symbol", observed=True).agg(
        mean_volume=("total_volume", "mean"),
        mean_trades=("num_trades", "mean")).reindex(order)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(order, g["mean_volume"], color=[PALETTE[s] for s in order])
    axes[0].set_title("Mean daily volume by instrument")
    axes[0].set_ylabel("Contracts/day"); axes[0].tick_params(axis="x", rotation=45)
    axes[1].bar(order, g["mean_trades"], color=[PALETTE[s] for s in order])
    axes[1].set_title("Mean daily number of trades by instrument")
    axes[1].set_ylabel("Trades/day"); axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig, g


def fig_open_interest(df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for s in _ordered(df):
        d = df[df["symbol"] == s]
        ax.plot(d["date"], d["mean_open_pos"], label=s, color=PALETTE[s], lw=1.3)
    ax.set_yscale("log")
    ax.set_title("Mean open interest over time (log scale)")
    ax.set_xlabel("Date"); ax.set_ylabel("Mean open interest (log)")
    ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    return fig


def return_correlation(df: pd.DataFrame):
    piv = df.pivot_table(index="date", columns="symbol", values="daily_return")
    piv = piv[_ordered(df)]
    corr = piv.corr()
    fig, ax = plt.subplots(figsize=(7.5, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0,
                vmin=-1, vmax=1, square=True, ax=ax,
                cbar_kws={"label": "Pearson r"})
    ax.set_title("Correlation of daily returns")
    fig.tight_layout()
    return corr, fig


def buysell_overview(df: pd.DataFrame):
    order = _ordered(df)
    tbl = df.groupby("symbol", observed=True).agg(
        mean_buy_share=("buy_share", "mean"),
        mean_imbalance=("direction_imbalance", "mean")).reindex(order)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].bar(order, tbl["mean_buy_share"], color=[PALETTE[s] for s in order])
    axes[0].axhline(0.5, color="red", ls="--", lw=1, label="balanced (0.5)")
    axes[0].set_title("Mean buy share (buy volume / total)")
    axes[0].set_ylim(0.4, 0.6); axes[0].legend()
    axes[0].tick_params(axis="x", rotation=45)
    axes[1].bar(order, tbl["mean_imbalance"], color=[PALETTE[s] for s in order])
    axes[1].set_title("Mean |buy share - 0.5| (direction imbalance)")
    axes[1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return tbl, fig


def hourly_activity(jan_csv=None, symbols=None, chunksize=4_000_000):
    """Compute the hourly profile from January raw trades."""
    jan_csv = jan_csv or os.path.join(INTERIM, "202501_fut_deal.csv")
    symbols = set(symbols or SYMBOL_ORDER)
    acc = {}
    vol = {}
    reader = pd.read_csv(jan_csv, usecols=["#SYMBOL", "MOMENT", "VOLUME"],
                         dtype={"#SYMBOL": "string", "MOMENT": "int64",
                                "VOLUME": "int64"}, chunksize=chunksize)
    for ch in reader:
        ch = ch[ch["#SYMBOL"].isin(symbols)]
        if ch.empty:
            continue
        hour = (ch["MOMENT"] // 10_000_000 % 100).astype("int16")
        c = hour.value_counts()
        v = ch.groupby(hour)["VOLUME"].sum()
        for h, n in c.items():
            acc[h] = acc.get(h, 0) + int(n)
        for h, n in v.items():
            vol[h] = vol.get(h, 0) + int(n)
    out = (pd.DataFrame({"trades": pd.Series(acc), "volume": pd.Series(vol)})
           .sort_index())
    out.index.name = "hour"
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(out.index, out["trades"], color="#4C72B0")
    ax.set_title("Intraday activity: number of trades by hour "
                 "(selected instruments, January 2025)")
    ax.set_xlabel("Hour of day"); ax.set_ylabel("Number of trades")
    ax.set_xticks(range(0, 24))
    fig.tight_layout()
    return out, fig


def hourly_activity_cached():
    """Use the saved hourly table when raw trades are not shipped with the app."""
    out = pd.read_csv(os.path.join(ROOT, "reports", "tables", "overview_hourly.csv"),
                      index_col=0)
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(out.index, out["trades"], color="#4C72B0")
    ax.set_title("Intraday activity: number of trades by hour "
                 "(selected instruments, January 2025) [precomputed]")
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Number of trades")
    ax.set_xticks(range(0, 24))
    fig.tight_layout()
    return out, fig


# Hypotheses
def hypothesis1(daily_all: pd.DataFrame, min_days=40, min_deals=50_000):
    """H1: compare liquidity and volatility across sufficiently active contracts."""
    d = daily_all.sort_values(["symbol", "date"]).copy()
    d["ret"] = (d.groupby("symbol", observed=True)["close_price"]
                .pct_change(fill_method=None) * 100)
    d["rel_range"] = (d["high_price"] - d["low_price"]) / d["close_price"] * 100
    g = d.groupby("symbol", observed=True)
    tab = pd.DataFrame({
        "num_days": g["date"].nunique(),
        "num_deals": g["num_trades"].sum(),
        "avg_volume": g["total_volume"].mean(),
        "avg_trades": g["num_trades"].mean(),
        "volatility": g["ret"].std(),
        "mean_rel_range": g["rel_range"].mean(),
    })
    tab = tab[(tab["num_days"] >= min_days) & (tab["num_deals"] >= min_deals)]
    tab = tab.dropna(subset=["volatility"])

    corr_rows = []
    for liq in ["avg_volume", "avg_trades"]:
        for vol in ["volatility", "mean_rel_range"]:
            x = np.log10(tab[liq]); y = tab[vol]
            pear = x.corr(y)
            spear = tab[liq].corr(tab[vol], method="spearman")
            corr_rows.append({"liquidity": liq, "volatility_metric": vol,
                              "pearson_logx": round(pear, 3),
                              "spearman": round(spear, 3)})
    corr = pd.DataFrame(corr_rows)

    fig, ax = plt.subplots(figsize=(9, 6))
    sizes = 20 + 120 * (tab["avg_trades"] / tab["avg_trades"].max())
    ax.scatter(tab["avg_volume"], tab["volatility"], s=sizes, alpha=.45,
               color="#4C72B0", edgecolor="k", linewidth=.3)
    for s in SYMBOL_ORDER:
        if s in tab.index:
            ax.annotate(s, (tab.loc[s, "avg_volume"], tab.loc[s, "volatility"]),
                        fontsize=8, color="darkred")
    ax.set_xscale("log")
    ax.set_title(f"H1: liquidity vs volatility ({len(tab)} contracts)\n"
                 "point size = avg trades/day")
    ax.set_xlabel("Avg daily volume (log scale)")
    ax.set_ylabel("Volatility = std of daily return, %")
    fig.tight_layout()
    return tab.sort_values("avg_volume", ascending=False), corr, fig


def _zscore_within(df, col):
    g = df.groupby("symbol", observed=True)[col]
    return (df[col] - g.transform("mean")) / g.transform("std")


def hypothesis2(df: pd.DataFrame, q=0.90):
    """H2: days with large price moves have higher trading activity.
    large_move_day = |return| above the per-instrument q-quantile."""
    d = df.dropna(subset=["abs_return"]).copy()
    thr = d.groupby("symbol", observed=True)["abs_return"].transform(
        lambda s: s.quantile(q))
    d["large_move"] = d["abs_return"] >= thr
    d["group"] = np.where(d["large_move"], "large-move", "normal")

    metrics = ["total_volume", "num_trades", "mean_open_pos", "volume_per_trade"]
    rows = []
    for m in metrics:
        for grp, sub in d.groupby("group", observed=True):
            rows.append({"metric": m, "group": grp,
                         "mean": sub[m].mean(), "median": sub[m].median(),
                         "std": sub[m].std()})
    table = pd.DataFrame(rows).pivot(index="metric", columns="group",
                                     values=["mean", "median", "std"])

    # Z-scores make volumes comparable across instruments with different scales.
    d["z_volume"] = _zscore_within(d, "total_volume")
    d["z_trades"] = _zscore_within(d, "num_trades")
    test = {}
    if HAVE_SCIPY:
        a = d.loc[d["large_move"], "z_volume"].dropna()
        b = d.loc[~d["large_move"], "z_volume"].dropna()
        u, p = _sps.mannwhitneyu(a, b, alternative="greater")
        test = {"mannwhitney_U": float(u), "p_value": float(p),
                "z_vol_large_mean": float(a.mean()),
                "z_vol_normal_mean": float(b.mean())}

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    sns.boxplot(data=d, x="group", y="z_volume", ax=axes[0],
                order=["normal", "large-move"], showfliers=False)
    axes[0].set_title("Within-instrument standardized volume")
    axes[0].set_xlabel(""); axes[0].set_ylabel("z-score of daily volume")
    sns.boxplot(data=d, x="group", y="z_trades", ax=axes[1],
                order=["normal", "large-move"], showfliers=False)
    axes[1].set_title("Within-instrument standardized #trades")
    axes[1].set_xlabel(""); axes[1].set_ylabel("z-score of #trades")
    fig.tight_layout()
    return table, test, fig


def hypothesis3(df: pd.DataFrame, q=0.90):
    """H3: compare order-flow imbalance on normal and high-volatility days."""
    d = df.dropna(subset=["abs_return", "direction_imbalance"]).copy()
    thr = d.groupby("symbol", observed=True)["abs_return"].transform(
        lambda s: s.quantile(q))
    d["group"] = np.where(d["abs_return"] >= thr, "high-vol", "normal")
    table = d.groupby("group", observed=True)["direction_imbalance"].agg(
        ["mean", "median", "std", "count"])
    test = {}
    if HAVE_SCIPY:
        a = d.loc[d["group"] == "high-vol", "direction_imbalance"]
        b = d.loc[d["group"] == "normal", "direction_imbalance"]
        u, p = _sps.mannwhitneyu(a, b, alternative="greater")
        test = {"mannwhitney_U": float(u), "p_value": float(p)}
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(data=d, x="group", y="direction_imbalance",
                order=["normal", "high-vol"], ax=ax, showfliers=False)
    ax.set_title("Direction imbalance: normal vs high-volatility days")
    ax.set_xlabel(""); ax.set_ylabel("|buy share - 0.5|")
    fig.tight_layout()
    return table, test, fig
