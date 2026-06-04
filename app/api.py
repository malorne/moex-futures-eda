#!/usr/bin/env python3
"""FastAPI service over the self-built aggregated daily dataset.

Run with:
    .venv/bin/uvicorn api:app --app-dir app --reload

Endpoints
  GET  /                  service info
  GET  /symbols           list contracts by liquidity (arg: limit)
  GET  /data              rows for a contract (args: symbol, limit, start/end date)
  GET  /stats/{symbol}    quick stats for a contract
  POST /data              DEMO: append a daily record to a local CSV
"""
import os
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

def _resolve_root() -> str:
    """Pick the first location that actually contains the aggregated data, so the
    service works under Docker (MOEX_ROOT=/app), Render's native runtime
    (/opt/render/project/src), Streamlit Cloud and locally - regardless of how
    MOEX_ROOT happens to be set."""
    here = os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    marker = os.path.join("data", "processed", "daily_year_2025.parquet")
    for cand in (os.environ.get("MOEX_ROOT"), here, os.getcwd()):
        if cand and os.path.exists(os.path.join(cand, marker)):
            return cand
    return os.environ.get("MOEX_ROOT") or here


ROOT = _resolve_root()
PROC = os.path.join(ROOT, "data", "processed")
APPEND_CSV = os.path.join(PROC, "api_appended.csv")

app = FastAPI(
    title="MOEX Futures EDA API",
    version="1.0",
    description="Read/append access to the self-built aggregated daily futures dataset "
                "(one row per contract per day). The raw 404M-trade files are not served.",
)


def _load() -> pd.DataFrame:
    df = pd.read_parquet(os.path.join(PROC, "daily_year_2025.parquet"))
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df["symbol"] = df["symbol"].astype(str)
    return df


DATA = _load()


class DailyRecord(BaseModel):
    date: str = Field(..., examples=["2025-06-02"])
    symbol: str = Field(..., examples=["IMOEXF"])
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    avg_price: Optional[float] = None
    total_volume: int
    num_trades: int
    mean_open_pos: Optional[float] = None
    max_open_pos: Optional[int] = None
    buy_volume: Optional[int] = 0
    sell_volume: Optional[int] = 0
    buy_count: Optional[int] = 0
    sell_count: Optional[int] = 0


@app.get("/")
def root():
    return {
        "service": "MOEX Futures EDA API",
        "rows": int(len(DATA)),
        "symbols": int(DATA["symbol"].nunique()),
        "date_range": [DATA["date"].min(), DATA["date"].max()],
        "endpoints": ["/symbols?limit=", "/data?symbol=&limit=&start_date=&end_date=",
                      "/stats/{symbol}", "POST /data"],
    }


@app.get("/symbols")
def symbols(limit: int = Query(20, ge=1, le=2000)):
    g = (DATA.groupby("symbol")["num_trades"].sum()
         .sort_values(ascending=False).head(limit))
    return [{"symbol": s, "total_trades": int(n)} for s, n in g.items()]


@app.get("/data")
def get_data(
    symbol: str = Query(..., description="contract code, e.g. IMOEXF"),
    limit: int = Query(100, ge=1, le=5000),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
):
    d = DATA[DATA["symbol"] == symbol]
    if d.empty:
        raise HTTPException(status_code=404, detail=f"symbol '{symbol}' not found")
    if start_date:
        d = d[d["date"] >= start_date]
    if end_date:
        d = d[d["date"] <= end_date]
    d = d.sort_values("date").head(limit)
    return {"symbol": symbol, "count": int(len(d)),
            "records": d.to_dict(orient="records")}


@app.get("/stats/{symbol}")
def stats(symbol: str):
    d = DATA[DATA["symbol"] == symbol].sort_values("date")
    if d.empty:
        raise HTTPException(status_code=404, detail=f"symbol '{symbol}' not found")
    close = pd.to_numeric(d["close_price"])
    ret = close.pct_change() * 100
    return {
        "symbol": symbol, "days": int(len(d)),
        "close_mean": float(close.mean()), "close_std": float(close.std()),
        "return_std_pct": float(ret.std()),
        "total_volume": int(pd.to_numeric(d["total_volume"]).sum()),
    }


@app.post("/data", status_code=201)
def add_record(rec: DailyRecord):
    """DEMO endpoint: appends the record to a local CSV
    (data/processed/api_appended.csv). It does NOT modify the source dataset —
    this simulates record creation so the API has a working POST method."""
    pd.DataFrame([rec.model_dump()]).to_csv(
        APPEND_CSV, mode="a", header=not os.path.exists(APPEND_CSV), index=False)
    n = sum(1 for _ in open(APPEND_CSV)) - 1
    return {"message": "record appended to local demo CSV (source data unchanged)",
            "stored_file": os.path.relpath(APPEND_CSV, ROOT),
            "total_appended": int(n), "record": rec.model_dump()}
