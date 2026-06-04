# Exploratory Data Analysis of MOEX Futures Market Trades in 2025
### Liquidity, Volatility and Open Interest

An end-to-end EDA project built **from raw exchange trade data**: ~404 million
individual MOEX (FORTS) futures trades for 2025 are downloaded, validated, and
aggregated by us into a clean daily dataset, then analysed with descriptive
statistics, comparative visualisations and three hypotheses. Deliverables: a Jupyter
notebook report, a Streamlit web app, and a FastAPI service.

> **Scope note.** We do **not** estimate theoretical derivative prices. The goal is
> exploratory data analysis of actual futures trade data: price dynamics, trading
> volume, number of trades, open interest, volatility and buy/sell activity.

---

## Data

* **Source:** MOEX derivatives market (FORTS), monthly `fut_deal` archives for
  2025 (`202501_fut_deal.7z` … `202512_fut_deal.7z`), obtained from a public
  Yandex.Disk folder.
* **Original grain:** one row per executed trade. Columns: `#SYMBOL, SYSTEM, MOMENT,
  ID_DEAL, PRICE_DEAL, VOLUME, OPEN_POS, DIRECTION` (`MOMENT` = `YYYYMMDDHHMMSSmmm`).
* **Volume:** 403,559,610 trades over the year; date coverage 2024-12-30 → 2025-12-30
  (each monthly file carries the previous day's evening session).
* **Quality:** 0 missing values, 0 duplicate `ID_DEAL`, no non-positive
  prices/volumes, no negative open interest — verified across all 12 months.
* **Aggregated grain (built by us):** one row per contract per day — `open/high/low/
  close/avg_price, total_volume, num_trades, mean/max_open_pos, buy/sell volume &
  counts`. 86,489 rows across 947 contracts.

### Selected instruments
The time-series analysis uses **seven liquid perpetual ("evergreen") futures** that
trade the whole year without expiry/roll, chosen by data (liquidity + completeness) and
spanning asset classes. *Ticker→underlying labels follow MOEX naming conventions and
should be confirmed against the official MOEX instrument reference.*

| Ticker | Asset class (per naming) |
|---|---|
| IMOEXF | Index (MOEX Index) |
| USDRUBF, CNYRUBF, EURRUBF | Currency (USD/CNY/EUR vs RUB) |
| GLDRUBF | Metal (Gold) |
| SBERF, GAZPF | Equity (Sberbank, Gazprom) |

---

## Project structure

```
moex/
├── data/
│   ├── raw/            # downloaded *_fut_deal.7z
│   ├── interim/        # extracted CSV (January kept for the hourly profile)
│   └── processed/      # daily_YYYYMM.parquet, daily_year_2025.parquet,
│                       # analysis_2025.parquet, symbol_summary.*, quality_*.json
├── scripts/
│   ├── yadisk.py               # Yandex.Disk public list/download (stdlib only)
│   ├── aggregate_fut_deal.py   # chunked quality profiling + daily aggregation (1 pass)
│   ├── build_year.py           # download + aggregate all 12 months (idempotent)
│   ├── build_features.py       # combine months, per-#SYMBOL summary, select set, features
│   ├── analysis_lib.py         # stats + plots + hypotheses (shared by notebook & app)
│   ├── make_report_artifacts.py# export every table (CSV) and figure (PNG)
│   └── build_notebook.py       # generates the notebook programmatically
├── notebooks/
│   └── moex_futures_eda.ipynb  # the report (executed, with outputs)
├── app/
│   ├── streamlit_app.py        # web interface mirroring the notebook
│   └── api.py                  # FastAPI service
├── reports/                    # figures/*.png, tables/*.csv, hypothesis_results.json
├── requirements.txt
└── README.md
```

---

## How to run

```bash
# 1) Environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2) Build the datasets from the raw archives (memory-safe, chunked)
.venv/bin/python scripts/build_year.py        # download + aggregate 12 months
.venv/bin/python scripts/build_features.py     # combine, select, engineer features
.venv/bin/python scripts/make_report_artifacts.py  # tables + figures (optional)

# 3) Report
.venv/bin/jupyter notebook notebooks/moex_futures_eda.ipynb

# 4) Web app (reads aggregated Parquet, not the raw files)
.venv/bin/streamlit run app/streamlit_app.py

# 5) REST API
.venv/bin/uvicorn api:app --app-dir app --reload
#   GET  /data?symbol=IMOEXF&limit=100&start_date=2025-06-01&end_date=2025-06-30
#   GET  /symbols?limit=10   |   GET /stats/IMOEXF
#   POST /data  (appends a record to a local demo CSV)
```

The pipeline never loads a full raw file into memory: each ~1.5–2.6 GB monthly CSV is
streamed in chunks (`pandas.read_csv(chunksize=...)`), aggregated, and the extracted
CSV is deleted before the next month.

---

## Key findings

* **H1 — "more liquid ⇒ lower volatility": NOT supported.** Across the contract
  universe, liquidity and volatility are essentially uncorrelated (|Pearson|,
  |Spearman| ≤ ~0.13).
* **H2 — "large-move days have higher activity": supported.** Volume/#trades are much
  higher on large-move days (Mann–Whitney p ≈ 5·10⁻³¹).
* **H3 — "imbalance higher on high-volatility days": supported (modestly)** (p ≈ 0.006).
* **Side finding:** MOEX weekend trading sessions appear from 2025-08-16 for
  equity/index/metal instruments but not for FX instruments.

All conclusions are derived only from the data; no external (news/macro) drivers are
claimed.

---

## How the grading criteria are covered

| # | Criterion | Where |
|---|---|---|
| 1 | Abstract / Annotation (≤2 paragraphs, goal, idea, contributions) | Notebook §1, Streamlit *Abstract* |
| 2 | Dataset description (domain, fields, types, quality; self-built emphasised) | Notebook §2, README, Streamlit *Dataset* |
| 3 | Descriptive statistics (≥4 fields; mean/median/std + quartiles) | Notebook §8 (`describe_overall`/`describe_by_symbol`) |
| 4 | Data cleanup (NaN, duplicates, types, datetime; proof if clean) | Notebook §5–6, `aggregate_fut_deal.py` |
| 5 | Plots for ≥4 numeric fields, ≥3 chart types | Notebook §9 (line, hist, scatter, box) |
| 6 | ≥4 comparison outputs (not single plots) | Notebook §10 (normalized multi-line, liquidity bars, OI, return-corr heatmap, hourly, buy/sell) |
| 7 | Data transformation (new columns) | Notebook §7 (`build_features.py`: 8+ features) |
| 8 | ≥2 non-trivial hypotheses, with stats + honest verdict | Notebook §11 (H1–H3, scipy tests) |
| 9 | Discussion after each step / each plot | Markdown after every section & figure |
| 10 | Streamlit web interface equivalent to the notebook | `app/streamlit_app.py` |
| 11 | FastAPI: ≥1 GET with ≥2 args, ≥1 POST | `app/api.py` (`GET /data`, `POST /data`) |

> Replace the placeholder author names (Team member 1–4) in the Abstract with the real
> team members and their contributions before submission.
