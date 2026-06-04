#!/usr/bin/env python3
"""Generate every table (CSV) and figure (PNG) used by the report / Streamlit
app, by calling analysis_lib. Running this end-to-end also validates the whole
analytical chain. Outputs go to reports/figures and reports/tables.
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis_lib as A  # noqa: E402

FIG = os.path.join(A.ROOT, "reports", "figures")
TAB = os.path.join(A.ROOT, "reports", "tables")


def _to_jsonable(o):
    if hasattr(o, "item"):
        return o.item()
    return str(o)


def save_fig(fig, name):
    fig.savefig(os.path.join(FIG, name), dpi=120, bbox_inches="tight")
    plt.close(fig)
    print("fig:", name)


def save_tab(df, name):
    df.to_csv(os.path.join(TAB, name))
    print("tab:", name)


def main():
    os.makedirs(FIG, exist_ok=True)
    os.makedirs(TAB, exist_ok=True)

    df = A.load_analysis()
    summ = A.load_summary()
    daily = A.load_daily_all()
    print(f"analysis rows={len(df)} symbols={df['symbol'].nunique()} "
          f"dates {df['date'].min().date()}..{df['date'].max().date()}")

    # ---- descriptive statistics ----
    save_tab(A.describe_overall(df), "describe_overall.csv")
    for f in ["close_price", "total_volume", "num_trades", "mean_open_pos",
              "daily_return", "relative_range", "volume_per_trade", "buy_share"]:
        save_tab(A.describe_by_symbol(df, f), f"by_symbol_{f}.csv")
    save_tab(summ.head(25), "symbol_summary_top25.csv")

    # ---- basic plots ----
    save_fig(A.fig_normalized_close(df), "basic_normalized_close.png")
    save_fig(A.fig_return_hist(df), "basic_return_hist.png")
    save_fig(A.fig_volume_vs_absreturn(df), "basic_volume_vs_absreturn.png")
    save_fig(A.fig_return_box(df), "basic_return_box.png")

    # ---- detailed comparative overview ----
    fig, gl = A.fig_liquidity_bars(df)
    save_fig(fig, "overview_liquidity.png")
    save_tab(gl, "overview_liquidity.csv")
    save_fig(A.fig_open_interest(df), "overview_open_interest.png")
    corr, fig = A.return_correlation(df)
    save_fig(fig, "overview_return_corr.png")
    save_tab(corr, "overview_return_corr.csv")
    tbl, fig = A.buysell_overview(df)
    save_fig(fig, "overview_buysell.png")
    save_tab(tbl, "overview_buysell.csv")
    try:
        hr, fig = A.hourly_activity()
        save_fig(fig, "overview_hourly.png")
        save_tab(hr, "overview_hourly.csv")
    except FileNotFoundError as e:
        print("hourly overview skipped (no January CSV):", e)

    # ---- hypotheses ----
    results = {}
    h1tab, h1corr, fig = A.hypothesis1(daily)
    save_fig(fig, "hyp1_liquidity_vol.png")
    save_tab(h1tab, "hyp1_table.csv")
    h1corr.to_csv(os.path.join(TAB, "hyp1_corr.csv"), index=False)
    results["H1_corr"] = h1corr.to_dict("records")

    h2tab, h2test, fig = A.hypothesis2(df)
    save_fig(fig, "hyp2_largemove.png")
    h2tab.to_csv(os.path.join(TAB, "hyp2_table.csv"))
    results["H2_test"] = h2test

    h3tab, h3test, fig = A.hypothesis3(df)
    save_fig(fig, "hyp3_imbalance.png")
    save_tab(h3tab, "hyp3_table.csv")
    results["H3_test"] = h3test

    with open(os.path.join(A.ROOT, "reports", "hypothesis_results.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=_to_jsonable)
    print("\n=== HYPOTHESIS RESULTS ===")
    print(json.dumps(results, ensure_ascii=False, indent=2, default=_to_jsonable))


if __name__ == "__main__":
    main()
