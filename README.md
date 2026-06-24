# MOEX Futures EDA 2025

Exploratory data analysis of MOEX futures trades in 2025.

Live version:

- Streamlit app: https://moex-futures-eda.streamlit.app
- FastAPI: https://moex-eda-api.onrender.com
- Swagger docs: https://moex-eda-api.onrender.com/docs

We worked with real MOEX FORTS trade data: monthly `fut_deal` archives for 2025.
The raw data contains about 404 million individual trades. For the analysis, we
validated the raw files, aggregated trades to daily contract-level rows, selected
liquid instruments, and studied liquidity, volatility, open interest and buy/sell
activity.

This is an EDA project, not a pricing model. We do not try to calculate fair
futures prices. The goal is to understand what is visible in the trading data.

## Data

The source data comes from MOEX derivatives market archives. Each raw row is one
executed trade with fields such as:

- `#SYMBOL`
- `MOMENT`
- `ID_DEAL`
- `PRICE_DEAL`
- `VOLUME`
- `OPEN_POS`
- `DIRECTION`

The raw files cover the period from `2024-12-30` to `2025-12-30`. After aggregation
we get one row per contract per day. The full daily dataset contains 86,489 rows
across 947 contracts.

During preprocessing we checked missing values, duplicated deal IDs, invalid prices,
invalid volumes and negative open interest. The data was clean enough to use after
type conversion and daily aggregation.

For the main time-series analysis we use seven liquid perpetual futures:

| Ticker | Group |
|---|---|
| `IMOEXF` | MOEX Index |
| `USDRUBF`, `CNYRUBF`, `EURRUBF` | Currency futures |
| `GLDRUBF` | Gold |
| `SBERF`, `GAZPF` | Equity futures |

The processed dataset includes prices, volume, number of trades, open interest,
buy/sell volumes and several derived features such as daily return, price range,
relative range and buy share.

## Main results

- More liquid contracts did not automatically have lower volatility. In the full
  contract universe the relationship between liquidity and volatility was weak.
- Large price-move days were usually linked with higher trading activity.
- Buy/sell imbalance was a bit higher on high-volatility days, but the effect was
  not very large.
- FX futures looked more stable and liquid in the selected group, while single-stock
  futures were generally more volatile.

## Project structure

```text
moex/
├── app/
│   ├── api.py
│   └── streamlit_app.py
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── notebooks/
│   └── moex_futures_eda.ipynb
├── reports/
├── scripts/
├── Dockerfile.api
├── Dockerfile.streamlit
├── docker-compose.yml
├── render.yaml
└── README.md
```

The main report is in `notebooks/moex_futures_eda.ipynb`. The Streamlit app follows
the same logic as the notebook, and the FastAPI service gives programmatic access
to the processed dataset.

## How to run locally

Create an environment and install dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Run the notebook:

```bash
.venv/bin/jupyter notebook notebooks/moex_futures_eda.ipynb
```

Run Streamlit:

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Run FastAPI:

```bash
.venv/bin/uvicorn api:app --app-dir app --reload
```

Then open:

- Streamlit: http://localhost:8501
- Swagger: http://localhost:8000/docs

If you need to rebuild the processed data from raw archives:

```bash
.venv/bin/python scripts/build_year.py
.venv/bin/python scripts/build_features.py
.venv/bin/python scripts/make_report_artifacts.py
```

The pipeline processes the raw files in chunks, so it does not load the whole
multi-gigabyte dataset into memory at once.

## API examples

List the most active symbols:

```bash
curl "https://moex-eda-api.onrender.com/symbols?limit=10"
```

Get rows for one contract:

```bash
curl "https://moex-eda-api.onrender.com/data?symbol=IMOEXF&limit=5&start_date=2025-06-01&end_date=2025-06-30"
```

Get quick statistics:

```bash
curl "https://moex-eda-api.onrender.com/stats/IMOEXF"
```

Create a demo record:

```bash
curl -X POST "https://moex-eda-api.onrender.com/data" \
  -H "Content-Type: application/json" \
  -d '{"date":"2025-06-02","symbol":"IMOEXF","open_price":100,"high_price":101,"low_price":99.5,"close_price":100.5,"total_volume":1234,"num_trades":56}'
```

The POST endpoint writes to a separate demo CSV file on the server. It does not
change the original analytical dataset.

## Docker and deployment

The repository includes Docker files for both services:

- `Dockerfile.api`
- `Dockerfile.streamlit`
- `docker-compose.yml`

To run both services with Docker:

```bash
docker compose up --build -d
```

Docker is used here to package the API and the Streamlit app in a reproducible way.
It is useful for deployment or for running the project on another machine without
manually recreating the Python environment.

One limitation: Docker images were not fully built in the authoring environment
because there was no Docker daemon available. The application code itself was tested
with the normal local start commands, and the public Streamlit/FastAPI services are
available online.

## Team

| Member | Contribution |
|---|---|
| Amirkhan Gareev | Data analysis, dataset exploration, feature engineering, descriptive statistics, EDA interpretation, figures and tables. |
| Timur Rozovel | Streamlit interface, FastAPI REST API, Docker/Render deployment, API testing, web interface validation. |
| Konstantin Ryadinskiy | Project coordination, README and final documentation, public URL integration, Streamlit visual check, final presentation preparation. |
