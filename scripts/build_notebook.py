#!/usr/bin/env python3
"""Build the project notebook.

Most calculations are kept in `analysis_lib.py`; this file assembles the report
cells in the order used for submission.
"""
import os
import nbformat as nbf

ROOT = os.environ.get("MOEX_ROOT") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "notebooks", "moex_futures_eda.ipynb")

nb = nbf.v4.new_notebook()
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))


def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip("\n")))


md(r"""
# Exploratory Data Analysis of MOEX Futures Market Trades in 2025
### Liquidity, Volatility and Open Interest

## 1. Abstract / Annotation

This project is an exploratory data analysis of MOEX futures trades in 2025. We start
from monthly raw `fut_deal` files with 403,559,610 individual trades, check the data
quality, aggregate trades to daily contract-level rows, and then study liquidity,
volatility, open interest and buy/sell activity for several liquid perpetual futures.
The goal is not to price derivatives, but to understand what the actual trading data
shows.

The report includes descriptive statistics, visual comparisons and three hypotheses.
In short, liquidity alone does not explain volatility across the whole contract
universe, large price moves are strongly connected with higher trading activity, and
buy/sell imbalance is slightly higher on high-volatility days. Team contribution:
Amirkhan Gareev — data analysis, dataset exploration, feature engineering,
descriptive statistics, EDA interpretation, figures and tables. Timur Rozovel —
Streamlit interface, FastAPI REST API, Docker/Render deployment, API testing and web
interface validation. Konstantin Ryadinskiy — project coordination, README and final
documentation, public URL integration, Streamlit visual check and final presentation
preparation.
""")

md(r"""
## 2. Dataset Description

**Subject area.** The data come from the **MOEX derivatives market (FORTS / срочный
рынок)** — the segment where futures and options on Russian financial instruments are
traded. We use only the **futures trade files** (`fut_deal`); options are out of scope.
The data were obtained as twelve monthly `7z` archives (`202501_fut_deal.7z` …
`202512_fut_deal.7z`, ≈145–251 MB compressed each, ≈1.5–2.6 GB uncompressed each) and
were **downloaded, decompressed, validated and aggregated by us** — i.e. the analytical
dataset is *self-built from raw exchange trades*, not a ready-made table.

**Original dataset — one row = one executed trade.** 8 fields:

| Field | Type | Meaning |
|---|---|---|
| `#SYMBOL` | string | Futures contract code (ticker) |
| `SYSTEM` | string | Trading system marker (constant `F`) |
| `MOMENT` | int (17 digits) | Trade timestamp `YYYYMMDDHHMMSSmmm` |
| `ID_DEAL` | int64 | Unique trade identifier |
| `PRICE_DEAL` | float | Trade price |
| `VOLUME` | int | Trade size (contracts) |
| `OPEN_POS` | int | Open interest after the trade |
| `DIRECTION` | string | Aggressor side: `B` (buy) or `S` (sell) |

**Aggregated dataset — one row = one contract on one trading day** (built by us). Base
fields: `date`, `symbol`, `open_price`, `high_price`, `low_price`, `close_price`,
`avg_price`, `total_volume`, `num_trades`, `mean_open_pos`, `max_open_pos`,
`buy_volume`, `sell_volume`, `buy_count`, `sell_count`. The full-year aggregated table
has **86,489 rows across 947 contracts** spanning **2024-12-30 → 2025-12-30**.

**Data quality.** The raw data are remarkably clean: across all 12 months there are
**0 missing values** in any column, **0 duplicate `ID_DEAL`**, **no non-positive
prices, no non-positive volumes, and no negative open interest**. `DIRECTION` only ever
takes `B`/`S`; `SYSTEM` is always `F`. The only non-obvious points, both handled
explicitly, are: (1) each monthly file starts with the **evening session of the
previous month's last trading day** (e.g. the January file begins on 2024-12-30
19:05), so the real date coverage extends slightly before each month; and (2) the
exchange runs **weekend sessions** for some instruments from 2025-08-16 onward. No
"wrong types" needed fixing — we read each column with an explicit dtype and parsed
`MOMENT` into a proper `datetime`.
""")

md("## 3. Data Loading\n\nWe load the self-built aggregated datasets (Parquet) and "
   "the per-month data-quality reports produced by the pipeline. The raw 404M-trade "
   "files are **never** loaded into memory here — they were processed in chunks by "
   "`scripts/aggregate_fut_deal.py`.")
code(r"""
import os, sys, json, glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

sys.path.insert(0, os.path.join('..', 'scripts'))
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))
import analysis_lib as A

pd.set_option('display.float_format', lambda x: f'{x:,.4f}')

daily_all = A.load_daily_all()       # all 947 contracts, one row per contract-day
df         = A.load_analysis()       # 7 selected perpetuals + engineered features
summary    = A.load_summary()        # per-#SYMBOL liquidity / quality metrics

print('daily_all:', daily_all.shape, '| contracts:', daily_all['symbol'].nunique())
print('analysis :', df.shape, '| instruments:', sorted(df['symbol'].unique()))
print('date range:', daily_all['date'].min().date(), '→', daily_all['date'].max().date())
""")
md("**Discussion.** Three tables drive the whole report: `daily_all` (the full "
   "contract universe, used for the broad liquidity-vs-volatility test), `df` (the "
   "seven selected instruments with engineered features, used for most plots and "
   "hypotheses), and `summary` (per-contract metrics used to *select* the instruments).")

md("## 4. Initial Data Overview")
code(r"""
# The raw file is large, so we only show a small sample here.
raw_sample = pd.read_csv('../data/interim/202501_fut_deal.csv', nrows=5)
print('Original trade-level data (first 5 rows):')
display(raw_sample)
print('Original columns:', list(raw_sample.columns))
""")
code(r"""
# This is the compact daily table used for analysis.
print('Aggregated daily data (head):')
display(daily_all.head())
print('\nDtypes:'); print(daily_all.dtypes)
""")
md("**Discussion.** The original file is genuine tick data — every executed trade with "
   "its price, size, post-trade open interest and aggressor side. Our aggregation turns "
   "those hundreds of millions of trades into a compact, analysis-ready daily table "
   "while preserving intraday extremes (high/low) and order-flow (buy/sell split).")

md("## 5. Data Quality Check\n\nWe summarise the per-month quality reports emitted by "
   "the pipeline and verify cleanliness directly on the aggregated table.")
code(r"""
qfiles = sorted(glob.glob('../data/processed/quality_2025*.json'))
rows = []
for f in qfiles:
    q = json.load(open(f)); m = os.path.basename(f)[8:14]
    rows.append({'month': m, 'trades': q['rows'], 'symbols': q['n_unique_symbols'],
                 'nan_total': sum(q['nan_by_column'].values()),
                 'dup_ID_DEAL': q['n_id_deal_duplicates'],
                 'price<=0': q['price_le0'], 'vol<=0': q['volume_le0'],
                 'open_int<0': q['open_pos_lt0']})
qtab = pd.DataFrame(rows)
display(qtab)
print(f"TOTAL trades over the year: {qtab['trades'].sum():,}")
print('Missing values anywhere:', int(qtab['nan_total'].sum()))
print('Duplicate trade IDs anywhere:', int(qtab['dup_ID_DEAL'].sum()))
print('Invalid prices/volumes/open-interest anywhere:',
      int(qtab[['price<=0','vol<=0','open_int<0']].to_numpy().sum()))
""")
code(r"""
# A second check on the final daily table.
print('NaN per column in aggregated daily dataset:')
print(daily_all.isna().sum().to_string())
print('\nDuplicate (symbol, date) rows:', int(daily_all.duplicated(['symbol','date']).sum()))

# Weekend sessions matter because they affect calendar interpretation.
ud = pd.Series(daily_all['date'].unique())
wknd = pd.to_datetime(ud)[pd.to_datetime(ud).dt.weekday >= 5].sort_values()
print('\nUnique trading dates:', ud.nunique(), '| of which weekend dates:', len(wknd))
print('First weekend session in the data:', wknd.min().date())
""")
md("**Discussion.** The exchange data are clean: **zero** missing values, **zero** "
   "duplicate trade IDs, and no impossible prices/volumes/open-interest across all "
   "**403,559,610** trades. Because the source is clean, our cleanup effort is minimal "
   "by design — the value we add is *constructing* the daily dataset and features. Two "
   "honest data nuances surface here: each month carries the prior day's evening "
   "session, and **weekend trading sessions appear from 2025-08-16** (visible as ~31 "
   "Saturday/Sunday dates).")

md("## 6. Data Cleanup\n\nWith the source already clean, cleanup reduces to *proving* "
   "cleanliness and ensuring correct types. The pipeline already (a) read every column "
   "with an explicit dtype, (b) parsed `MOMENT` (`YYYYMMDDHHMMSSmmm`) into `datetime`, "
   "and (c) merged the few contract-days that appear in two monthly files at the "
   "month boundary.")
code(r"""
# These assertions make the cleanup result explicit.
assert daily_all.isna().sum().sum() == 0, 'unexpected NaNs'
assert daily_all.duplicated(['symbol','date']).sum() == 0, 'unexpected dup keys'
assert str(daily_all['date'].dtype).startswith('datetime'), 'date not datetime'
assert (daily_all[['open_price','high_price','low_price','close_price']] > 0).all().all()
assert (daily_all['total_volume'] > 0).all() and (daily_all['num_trades'] > 0).all()
print('All cleanliness assertions passed: no NaN, no duplicate keys, datetime dates,'
      ' strictly positive prices/volume/trades.')
""")
md("**Discussion.** All assertions pass, so no rows are dropped or imputed. This is the "
   "'data are already clean — here is the proof' path. The single transformation that "
   "*could* create duplicates (concatenating monthly files) is handled by a "
   "trade-weighted merge in `build_features.py`.")

md(r"""
## 7. Feature Engineering / Data Transformation

From the base daily fields we derive features for the seven selected instruments:

| Feature | Definition |
|---|---|
| `daily_return` | % change of `close_price` within each `symbol` |
| `abs_return` | `|daily_return|` |
| `price_range` | `high_price − low_price` |
| `relative_range` | `price_range / close_price · 100` (%) |
| `volume_per_trade` | `total_volume / num_trades` |
| `buy_share` | `buy_volume / (buy_volume + sell_volume)` |
| `direction_imbalance` | `|buy_share − 0.5|` |
| `normalized_close` | `close_price / first_close_of_symbol · 100` |
| `month`, `weekday` | calendar parts of `date` |

Intraday parts (`hour`, `minute`) are **not** available after daily aggregation; we
compute an hourly profile separately from the raw January file in the detailed overview.
""")
code(r"""
feat_cols = ['symbol','date','close_price','daily_return','abs_return',
             'relative_range','volume_per_trade','buy_share',
             'direction_imbalance','normalized_close']
display(df[feat_cols].head(8))
print('Engineered analysis dataset:', df.shape,
      '| instruments:', df['symbol'].nunique(),
      '| asset classes:', sorted(df['asset_class'].unique()))
""")
md("**Discussion.** `daily_return`/`abs_return` capture price dynamics and volatility; "
   "`relative_range` is a scale-free intraday-range proxy; `volume_per_trade` and the "
   "`buy_share`/`direction_imbalance` pair describe liquidity texture and order-flow; "
   "`normalized_close` rebases every instrument to 100 so series on very different "
   "price scales can be compared on one chart.")

md("## 8. Descriptive Statistics\n\nWe report mean, median and standard deviation "
   "(plus min/max and quartiles) for the key numeric fields — overall and per "
   "instrument.")
code(r"""
display(A.describe_overall(df).round(4))
""")
code(r"""
print('Per-instrument statistics for daily_return (%):')
display(A.describe_by_symbol(df, 'daily_return').round(4))
print('Per-instrument statistics for total_volume:')
display(A.describe_by_symbol(df, 'total_volume').round(1))
""")
md("**Discussion.** Mean daily returns are close to zero for all instruments (as "
   "expected for price changes), while the standard deviation of returns — our "
   "volatility proxy — is clearly larger for single-stock futures than for FX. Volume "
   "distributions are highly right-skewed (mean ≫ median), typical of trading activity "
   "with occasional very busy days.")

md("## 9. Basic Visualizations\n\nFour numeric fields, four chart types: line, "
   "histogram, scatter, box.")
code("fig = A.fig_normalized_close(df); display(fig); plt.close(fig)")
md("**What it shows.** Rebased to 100 on the first day, the instruments diverge over "
   "the year; equity/index lines move in a wider band than the FX lines, a first visual "
   "hint that equities are more volatile than currencies.")
code("fig = A.fig_return_hist(df); display(fig); plt.close(fig)")
md("**What it shows.** Pooled daily returns are roughly symmetric and centred near "
   "zero with fat tails (large moves occur more often than a normal distribution would "
   "predict) — relevant for the large-move hypothesis later.")
code("fig = A.fig_volume_vs_absreturn(df); display(fig); plt.close(fig)")
md("**What it shows.** On a log-volume axis, larger absolute returns tend to coincide "
   "with higher daily volume — a visual preview of Hypothesis 2.")
code("fig = A.fig_return_box(df); display(fig); plt.close(fig)")
md("**What it shows.** Box widths (IQR) and whiskers rank the instruments by "
   "volatility: single-stock futures (GAZPF, SBERF) are widest, FX futures the "
   "tightest, with the index and gold in between.")

md("## 10. Detailed Comparative Overview\n\nFive comparative views: normalized prices, "
   "liquidity, open interest, return correlations, and intraday activity.")
code(r"""
# Normalized prices were shown above; here we compare liquidity directly.
fig, gtab = A.fig_liquidity_bars(df); display(gtab.round(0)); display(fig); plt.close(fig)
""")
md("**What it shows.** The index and FX perpetuals dominate both average daily volume "
   "and average number of trades; the single-stock perpetuals are an order of magnitude "
   "thinner.")
code(r"""
fig = A.fig_open_interest(df); display(fig); plt.close(fig)
""")
md("**What it shows.** Open interest (log scale) is highest and steadiest for the FX "
   "and index contracts and lower for single stocks, consistent with the liquidity "
   "ranking above.")
code(r"""
corr, fig = A.return_correlation(df); display(corr.round(2)); display(fig); plt.close(fig)
""")
md("**What it shows.** Daily-return correlations are high among the FX perpetuals "
   "(they share the rouble as the common factor), moderate between the index and the "
   "two stocks, and low between FX and equities — i.e. the chosen instruments are "
   "genuinely diversified.")
code(r"""
tab, fig = A.buysell_overview(df); display(tab.round(3)); display(fig); plt.close(fig)
""")
md("**What it shows.** Average buy share sits close to 0.5 for every instrument "
   "(balanced aggressor flow), with small, instrument-specific imbalances.")
code(r"""
hourly, fig = A.hourly_activity(); display(hourly); display(fig); plt.close(fig)
""")
md("**What it shows.** Intraday (January) activity is concentrated in the main daytime "
   "session, with a secondary bump during the evening session — the classic MOEX "
   "two-session trading day.")

md(r"""
## 11. Hypothesis Testing

We test three hypotheses that go beyond a single two-group comparison. For each we
report a statistic and a figure and state honestly whether the data support it.
""")
md(r"""
### Hypothesis 1 — *More liquid futures contracts have lower volatility.*
Tested across **all sufficiently-liquid contracts** (not only the seven), correlating
two liquidity measures (avg daily volume, avg daily #trades) with two volatility
measures (std of daily return, mean relative range).
""")
code(r"""
h1_tab, h1_corr, fig = A.hypothesis1(daily_all)
print('Liquidity vs volatility correlations (n = %d contracts):' % len(h1_tab))
display(h1_corr)
display(fig); plt.close(fig)
""")
md("**Conclusion (H1): not supported.** All correlations are essentially zero "
   "(|Pearson|, |Spearman| ≤ ~0.13). In this dataset there is **no meaningful "
   "negative relationship** between liquidity and volatility across contracts — the "
   "intuitive 'more liquid ⇒ calmer' idea does not hold here. We report the result "
   "without inventing external causes.")
md(r"""
### Hypothesis 2 — *Days with large price movements have higher trading activity.*
`large_move_day` = a day whose `|return|` is in the **top 10%** for that instrument.
We compare activity on large-move vs normal days and, to remove scale differences,
use the within-instrument **z-score** of volume with a Mann–Whitney U test.
""")
code(r"""
h2_tab, h2_test, fig = A.hypothesis2(df, q=0.90)
display(h2_tab.round(2))
print('Mann-Whitney U (z-volume, large-move > normal):', h2_test)
display(fig); plt.close(fig)
""")
md("**Conclusion (H2): supported.** Mean/median volume, number of trades and "
   "volume-per-trade are all clearly higher on large-move days, and the standardized "
   "volume is significantly higher (p ≈ 5·10⁻³¹). Large price moves and high trading "
   "activity go together in these data.")
md(r"""
### Hypothesis 3 — *Buy/sell imbalance is higher on high-volatility days.*
Same top-10% split by `|return|`, comparing `direction_imbalance` (`|buy_share − 0.5|`).
""")
code(r"""
h3_tab, h3_test, fig = A.hypothesis3(df, q=0.90)
display(h3_tab.round(4))
print('Mann-Whitney U (imbalance, high-vol > normal):', h3_test)
display(fig); plt.close(fig)
""")
md("**Conclusion (H3): supported (modestly).** Direction imbalance is higher on "
   "high-volatility days (p ≈ 0.006). On turbulent days aggressor flow leans a little "
   "more to one side, though the effect is small compared with H2.")

md(r"""
## 12. Discussion

Putting the pieces together, the seven instruments form a clear **liquidity/volatility
ordering**: FX perpetuals are the most liquid and the calmest; single-stock perpetuals
are the thinnest and the most volatile; the index and gold sit in between. Yet *across
the broad contract universe* liquidity does **not** predict volatility (H1) — the
ordering we see among the seven is driven by **asset class**, not by liquidity per se.
Activity, however, is tightly linked to **price movement**: large-move days are
high-volume days (H2), and order flow becomes slightly more one-sided when volatility
is high (H3). The return-correlation structure confirms the instruments are
diversified (FX cluster vs equity cluster), and the data also reveal exchange
micro-structure facts — a two-session trading day and the 2025 introduction of weekend
sessions for non-FX instruments. All statements above are derived **only** from the
data; we make no claims about external (news/macro) drivers, which are not in the dataset.
""")
md(r"""
## 13. Conclusion

We built, from ~404 million raw MOEX futures trades, a clean self-constructed daily
dataset and a feature set, and used them for a full EDA. Two of three hypotheses were
supported (large moves ↔ activity; imbalance ↔ volatility) and one was rejected
(liquidity ↔ volatility). The project demonstrates a memory-safe pipeline (chunked
reading, aggregation, Parquet outputs), honest data-quality reporting, comparative
visual analysis, and statistically-backed hypothesis testing.
""")
md(r"""
## 14. Limitations

- **Scope:** futures only (`fut_deal`); options and the full order log (`fut_log`) were
  excluded by design. Analysis is one calendar year (2025), so seasonal claims are
  limited to a single year.
- **Perpetual instruments:** the seven analysed contracts are *evergreen* perpetual
  futures, chosen for clean year-long coverage; expiry-coded quarterly contracts (which
  roll) are summarised but not used for the time-series analysis.
- **Daily aggregation** discards intraday structure (except the separate hourly
  profile). Open interest is summarised per day (mean/max), not as an end-of-day snapshot.
- **Weekend sessions / month-boundary evening sessions** add a few extra dates for some
  instruments; returns around these are kept as-is and flagged rather than removed.
- **Hypothesis tests** are descriptive/associational, not causal; ticker→underlying
  labels follow MOEX naming conventions and should be confirmed against the official
  MOEX instrument reference.
""")
md(r"""
## 15. Web Interface Description

The same content is delivered as a **Streamlit** app (`app/streamlit_app.py`) with
sidebar navigation mirroring this notebook (Abstract, Dataset, Cleaning, Statistics,
Plots, Detailed Overview, Hypotheses, Discussion). It reads the **aggregated Parquet**
files (not the raw archives), so it is lightweight. A small **FastAPI** service
(`app/api.py`) exposes the aggregated data: a `GET /data` endpoint filtering by
`symbol` + `limit` (and optional date range), `GET /symbols`, `GET /stats/{symbol}`,
and a demo `POST /data` that appends a record to a local CSV.
""")

nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"display_name": "Python (moex)",
                                "language": "python", "name": "moex-venv"}
nb["metadata"]["language_info"] = {"name": "python"}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print("wrote", OUT, "with", len(cells), "cells")
