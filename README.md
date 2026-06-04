# Exploratory Data Analysis of MOEX Futures Market Trades in 2025
### Liquidity, Volatility and Open Interest

**🌐 Live demo (deployed & verified over the Internet):**
[Streamlit app](https://moex-futures-eda.streamlit.app) ·
[FastAPI](https://moex-eda-api.onrender.com) ·
[Swagger docs](https://moex-eda-api.onrender.com/docs)

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
├── Dockerfile.api              # FastAPI image
├── Dockerfile.streamlit        # Streamlit image
├── docker-compose.yml          # both services (streamlit:8501, api:8000)
├── render.yaml                 # Render.com Blueprint (both services)
├── Procfile                    # Heroku/Render native start (API)
├── .streamlit/config.toml      # headless server config
├── requirements.txt            # lean RUNTIME deps (apps; used by Streamlit Cloud)
├── requirements-app.txt        # same lean set, used by the Docker images
├── requirements-dev.txt        # full pipeline/notebook deps (superset)
└── README.md
```

---

## How to run (local development)

```bash
# 1) Environment  (apps need requirements.txt; full pipeline/notebook needs requirements-dev.txt)
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt

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

## Web deployment

**🌐 Live public deployment (verified over the Internet):**

| Service | Public URL | Status |
|---|---|---|
| Streamlit app | https://moex-futures-eda.streamlit.app | HTTP 200 |
| FastAPI | https://moex-eda-api.onrender.com | HTTP 200 |
| Swagger docs | https://moex-eda-api.onrender.com/docs | HTTP 200 |

Both services read only the aggregated `data/processed/*.parquet` (~11 MB); the
multi-GB raw archives are never shipped. The app is also containerised to run
locally or on any VPS (below).

> Render's free tier sleeps after ~15 min idle; the first request then takes ~50 s
> (cold start), subsequent requests are fast. The `POST /data` demo writes to an
> ephemeral file that resets on redeploy — the source dataset is never modified.

| Service | Local URL | Container port |
|---|---|---|
| Streamlit app | http://localhost:8501 | 8501 |
| FastAPI + Swagger | http://localhost:8000/docs | 8000 |

**Option A — Docker on any VPS/server (self-host, recommended):**

```bash
docker compose up --build -d     # build both images, run detached
docker compose ps                # status   |   docker compose logs -f
docker compose down              # stop
```

Open it:

```text
Local machine:    http://localhost:8501        http://localhost:8000/docs
Server public IP: http://SERVER_IP:8501        http://SERVER_IP:8000/docs
Via a domain:     https://your-domain          https://your-domain/docs   (reverse proxy)
```

**Option B — FastAPI on Render.com (free public URL):** push this repo to GitHub,
then Render → *New → Blueprint* → select the repo (`render.yaml` defines both Docker
web services; `$PORT` is injected automatically). The API alone can also be deployed
with `Dockerfile.api` or `Procfile`.

**Option C — Streamlit on Streamlit Community Cloud (free public URL):** push to
GitHub, then share.streamlit.io → *New app* → main file `app/streamlit_app.py`,
requirements `requirements.txt`. The committed Parquet + `reports/` tables make the
app fully functional online (the hourly chart falls back to a precomputed table).

Live endpoints (verified over the Internet):

```text
### Streamlit app
Public URL: https://moex-futures-eda.streamlit.app            (HTTP 200)

### FastAPI
Public API URL: https://moex-eda-api.onrender.com             (HTTP 200)
Swagger docs:   https://moex-eda-api.onrender.com/docs        (HTTP 200)

Example GET:
  https://moex-eda-api.onrender.com/data?symbol=IMOEXF&limit=10
Example POST:
  curl -X POST https://moex-eda-api.onrender.com/data -H "Content-Type: application/json" \
    -d '{"date":"2025-06-02","symbol":"IMOEXF","open_price":100,"high_price":101,
         "low_price":99.5,"close_price":100.5,"total_volume":1234,"num_trades":56}'
```

---

## Web interface status

```text
Local development (BUILT AND TESTED in this environment):
- Streamlit:    http://localhost:8501       -> all 8 pages render without errors
- FastAPI:      http://localhost:8000       -> all endpoints return expected codes
- Swagger docs: http://localhost:8000/docs  -> loads (HTTP 200)
  Checked: GET / (200), GET /symbols (200), GET /data?symbol=&limit= (200),
           GET /stats/{symbol} (200; 404 for unknown), POST /data (201), /docs (200)

Prepared for deployment (files present; `docker compose config` validated):
- Dockerfile.api, Dockerfile.streamlit, docker-compose.yml
- render.yaml (Render Blueprint), Procfile, .streamlit/config.toml, requirements-app.txt
- git repo initialised with an initial commit (ready to push to GitHub)

Public deployment (LIVE over the Internet — verified):
- Streamlit app: https://moex-futures-eda.streamlit.app        -> HTTP 200 (app shell served)
- FastAPI:       https://moex-eda-api.onrender.com             -> HTTP 200
- Swagger docs:  https://moex-eda-api.onrender.com/docs        -> HTTP 200
  Verified public API checks: GET / (200), /symbols (200), /data?symbol=&limit= (200),
  /data + date range (200), /stats/{symbol} (200; 404 unknown), POST /data (201),
  /docs (200), /openapi.json (200).
  (Streamlit page content renders client-side; the deployed commit is the same one whose
   8 pages passed Streamlit AppTest, with the underlying data proven live via the API.)

Deployed via: GitHub (github.com/malorne/moex-futures-eda) -> Render (FastAPI) +
Streamlit Community Cloud (UI).
```

> Docker images could not be **built** inside the authoring environment (no Docker
> daemon), so the container build itself is unverified there; the Compose file is
> syntactically validated and the apps are verified to run via the same start commands.

### Public Streamlit visual check

All 8 sidebar sections were opened on the **public** app
(https://moex-futures-eda.streamlit.app) in a headless browser and full-page
screenshotted — **8/8 render without errors**. Images are in `reports/screenshots/`
(reproducible via `scripts/streamlit_visual_check.py`, which needs `playwright`).

| # | Page | Screenshot | Result |
|---|---|---|---|
| 1 | Abstract | `reports/screenshots/01_Abstract.png` | ✅ |
| 2 | Dataset Description | `reports/screenshots/02_Dataset_Description.png` | ✅ |
| 3 | Data Cleaning | `reports/screenshots/03_Data_Cleaning.png` | ✅ |
| 4 | Descriptive Statistics | `reports/screenshots/04_Descriptive_Statistics.png` | ✅ |
| 5 | Basic Plots | `reports/screenshots/05_Basic_Plots.png` | ✅ |
| 6 | Detailed Overview | `reports/screenshots/06_Detailed_Overview.png` | ✅ |
| 7 | Hypothesis Testing | `reports/screenshots/07_Hypothesis_Testing.png` | ✅ |
| 8 | Discussion / Conclusion | `reports/screenshots/08_Discussion_Conclusion.png` | ✅ |

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
| 12 | Web deployment (containerised, public-ready) | `Dockerfile.*`, `docker-compose.yml`, `render.yaml`, `Procfile`, `.streamlit/`, *Web deployment* section |

---

## Team

| Member | Contribution |
|---|---|
| **Amirkhan Gareev** | Data analysis, dataset exploration, feature engineering, descriptive statistics, EDA interpretation, figures and tables. |
| **Timur Rozovel** | Streamlit interface, FastAPI REST API, Docker/Render deployment, API testing, web interface validation. |
| **Konstantin Ryadinskiy** | Project coordination, README and final documentation, public URL integration, Streamlit visual check, final presentation preparation. |
