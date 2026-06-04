#!/usr/bin/env python3
"""Streamlit web interface for the MOEX Futures EDA project.

Mirrors the Jupyter notebook section-by-section. Reads the *aggregated* Parquet
datasets (never the raw archives), so it stays lightweight. Run with:

    .venv/bin/streamlit run app/streamlit_app.py
"""
import os
import sys
import glob
import json

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import analysis_lib as A  # noqa: E402

st.set_page_config(page_title="MOEX Futures EDA 2025", layout="wide")


@st.cache_data(show_spinner=False)
def load_data():
    return A.load_daily_all(), A.load_analysis(), A.load_summary()


@st.cache_data(show_spinner=False)
def load_quality():
    rows = []
    for f in sorted(glob.glob(os.path.join(A.PROC, "quality_2025*.json"))):
        q = json.load(open(f))
        rows.append({"month": os.path.basename(f)[8:14], "trades": q["rows"],
                     "symbols": q["n_unique_symbols"],
                     "nan_total": sum(q["nan_by_column"].values()),
                     "dup_ID_DEAL": q["n_id_deal_duplicates"],
                     "price<=0": q["price_le0"], "vol<=0": q["volume_le0"],
                     "open_int<0": q["open_pos_lt0"]})
    return pd.DataFrame(rows)


daily_all, df, summary = load_data()

st.sidebar.title("MOEX Futures EDA 2025")
PAGES = ["Abstract", "Dataset Description", "Data Cleaning",
         "Descriptive Statistics", "Basic Plots", "Detailed Overview",
         "Hypothesis Testing", "Discussion / Conclusion"]
page = st.sidebar.radio("Navigation", PAGES)
st.sidebar.markdown("---")
st.sidebar.caption("Instruments (perpetual futures):")
st.sidebar.write({s: A.ASSET_CLASS[s] for s in A.SYMBOL_ORDER})
st.sidebar.caption("Data: self-built daily aggregation of ~404M MOEX futures trades "
                   "(2024-12-30 → 2025-12-30).")


def show_fig(fig):
    st.pyplot(fig)
    plt.close(fig)


# --------------------------------------------------------------------------- #
if page == "Abstract":
    st.title("EDA of MOEX Futures Market Trades in 2025")
    st.subheader("Liquidity, Volatility and Open Interest")
    st.markdown(
        "This project is an exploratory data analysis of **trade-level data from the "
        "MOEX derivatives market (FORTS)** for 2025. From the raw monthly `fut_deal` "
        "files (**403,559,610 trades**) we built a memory-safe pipeline that streams "
        "the `.7z` archives in chunks, checks data quality, and aggregates trades into "
        "a clean **daily dataset** (one row per contract-day). We then engineer "
        "return/volatility/liquidity/order-flow features and analyse **seven liquid "
        "perpetual futures** across asset classes (index, FX, gold, single stocks).")
    st.info("We do **not** estimate theoretical derivative prices. The goal is EDA of "
            "actual futures trade data: price dynamics, volume, number of trades, open "
            "interest, volatility and buy/sell activity.")
    st.markdown(
        "**Main findings:** H1 (liquid ⇒ less volatile) is **not supported** "
        "(near-zero correlation); H2 (large-move days ⇒ higher activity) is "
        "**supported** (p ≈ 5·10⁻³¹); H3 (imbalance higher on high-vol days) is "
        "**supported** (p ≈ 0.006).")
    st.markdown("**Team contributions (placeholders):** Member 1 — pipeline & cleaning; "
                "Member 2 — features & statistics; Member 3 — visualisation & "
                "hypotheses; Member 4 — web interfaces & report.")

elif page == "Dataset Description":
    st.title("Dataset Description")
    st.markdown(
        "**Subject area:** MOEX derivatives market (futures). Source: twelve monthly "
        "`fut_deal` `.7z` archives (≈2.3 GB compressed), **downloaded, decompressed and "
        "aggregated by us** — the analytical dataset is self-built from raw trades.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Original dataset — one row = one trade (8 fields)**")
        st.table(pd.DataFrame({
            "field": ["#SYMBOL", "SYSTEM", "MOMENT", "ID_DEAL", "PRICE_DEAL",
                      "VOLUME", "OPEN_POS", "DIRECTION"],
            "meaning": ["contract code", "system (=F)", "YYYYMMDDHHMMSSmmm",
                        "trade id", "price", "size", "open interest", "B / S"]}))
    with c2:
        st.markdown("**Aggregated dataset — one row = one contract-day (built by us)**")
        st.write(f"Rows: **{len(daily_all):,}** · contracts: "
                 f"**{daily_all['symbol'].nunique()}** · dates "
                 f"{daily_all['date'].min().date()} → {daily_all['date'].max().date()}")
        st.dataframe(daily_all.head(12), width='stretch')
    st.markdown("**Per-#SYMBOL liquidity / quality metrics (top 25 by deals):**")
    st.dataframe(summary.head(25), width='stretch')

elif page == "Data Cleaning":
    st.title("Data Quality & Cleaning")
    q = load_quality()
    st.dataframe(q, width='stretch')
    a, b, c = st.columns(3)
    a.metric("Total trades", f"{q['trades'].sum():,}")
    b.metric("Missing values (all months)", int(q["nan_total"].sum()))
    c.metric("Duplicate trade IDs", int(q["dup_ID_DEAL"].sum()))
    st.success("Source data are clean: 0 missing values, 0 duplicate IDs, no "
               "non-positive prices/volumes and no negative open interest across all "
               "403.5M trades. Cleanup is therefore minimal — the value added is "
               "*constructing* the daily dataset and features.")
    st.markdown("**NaN per column in the aggregated dataset:**")
    st.write(daily_all.isna().sum().to_dict())
    ud = pd.Series(daily_all["date"].unique())
    wknd = pd.to_datetime(ud)[pd.to_datetime(ud).dt.weekday >= 5]
    st.markdown(f"**Data nuance:** {len(wknd)} weekend trading dates appear from "
                f"**{pd.to_datetime(wknd).min().date()}** (MOEX weekend sessions for "
                "non-FX instruments).")

elif page == "Descriptive Statistics":
    st.title("Descriptive Statistics")
    st.markdown("Overall statistics (mean, median, std, min/max, quartiles):")
    st.dataframe(A.describe_overall(df).round(4), width='stretch')
    field = st.selectbox("Per-instrument statistics for field:",
                         ["daily_return", "close_price", "total_volume",
                          "num_trades", "mean_open_pos", "relative_range",
                          "volume_per_trade", "buy_share"])
    st.dataframe(A.describe_by_symbol(df, field).round(4), width='stretch')

elif page == "Basic Plots":
    st.title("Basic Visualizations")
    st.markdown("**Normalized close (first day = 100)** — line chart")
    show_fig(A.fig_normalized_close(df))
    st.markdown("**Distribution of daily returns** — histogram")
    show_fig(A.fig_return_hist(df))
    st.markdown("**Daily volume vs |daily return|** — scatter (log volume)")
    show_fig(A.fig_volume_vs_absreturn(df))
    st.markdown("**Daily return by instrument** — boxplot")
    show_fig(A.fig_return_box(df))

elif page == "Detailed Overview":
    st.title("Detailed Comparative Overview")
    st.markdown("**Liquidity:** mean daily volume and mean #trades by instrument")
    fig, gtab = A.fig_liquidity_bars(df)
    st.dataframe(gtab.round(0), width='stretch')
    show_fig(fig)
    st.markdown("**Open interest over time (log scale)**")
    show_fig(A.fig_open_interest(df))
    st.markdown("**Correlation of daily returns**")
    corr, fig = A.return_correlation(df)
    st.dataframe(corr.round(2), width='stretch')
    show_fig(fig)
    st.markdown("**Buy/sell activity and direction imbalance**")
    tab, fig = A.buysell_overview(df)
    st.dataframe(tab.round(3), width='stretch')
    show_fig(fig)
    st.markdown("**Intraday activity by hour (January, raw trades)**")
    hourly, fig = None, None
    try:
        hourly, fig = A.hourly_activity()           # from raw CSV if available
    except FileNotFoundError:
        try:
            hourly, fig = A.hourly_activity_cached()  # precomputed table fallback
        except FileNotFoundError:
            pass
    if fig is not None:
        st.dataframe(hourly, width='stretch')
        show_fig(fig)
    else:
        st.warning("Hourly profile unavailable (no raw CSV and no cached table).")

elif page == "Hypothesis Testing":
    st.title("Hypothesis Testing")
    st.header("H1 — More liquid contracts have lower volatility")
    h1_tab, h1_corr, fig = A.hypothesis1(daily_all)
    st.dataframe(h1_corr, width='stretch')
    show_fig(fig)
    st.error("**Not supported** — all correlations are ≈0; liquidity does not predict "
             "volatility across the contract universe.")

    st.header("H2 — Large-move days have higher trading activity")
    h2_tab, h2_test, fig = A.hypothesis2(df, q=0.90)
    st.dataframe(h2_tab.round(2), width='stretch')
    st.write(h2_test)
    show_fig(fig)
    st.success("**Supported** — volume/#trades are much higher on large-move days "
               "(Mann-Whitney p ≈ 5·10⁻³¹).")

    st.header("H3 — Imbalance is higher on high-volatility days")
    h3_tab, h3_test, fig = A.hypothesis3(df, q=0.90)
    st.dataframe(h3_tab.round(4), width='stretch')
    st.write(h3_test)
    show_fig(fig)
    st.success("**Supported (modestly)** — direction imbalance is higher on high-vol "
               "days (p ≈ 0.006).")

elif page == "Discussion / Conclusion":
    st.title("Discussion & Conclusion")
    st.markdown(
        "- The seven instruments form a clear **asset-class** ordering of "
        "liquidity/volatility: FX perpetuals are most liquid and calmest; single-stock "
        "perpetuals are thinnest and most volatile; index and gold sit in between.\n"
        "- Yet across the **broad** contract universe, liquidity does **not** predict "
        "volatility (H1) — the ordering is driven by asset class, not liquidity.\n"
        "- Trading **activity tracks price movement**: large-move days are high-volume "
        "days (H2), and order flow is slightly more one-sided on high-volatility days "
        "(H3).\n"
        "- Return correlations confirm the instruments are **diversified** (FX cluster "
        "vs equity cluster).\n"
        "- Micro-structure facts emerge from the data: a two-session trading day and "
        "the **2025 launch of weekend sessions** for non-FX instruments.")
    st.info("All conclusions are derived only from the data. We make no claims about "
            "external (news/macro) drivers, which are not part of the dataset. "
            "Ticker→underlying labels follow MOEX naming and should be confirmed "
            "against the official MOEX instrument reference.")
