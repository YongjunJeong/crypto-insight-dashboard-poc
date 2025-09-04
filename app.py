import os
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st
from databricks import sql
from dotenv import load_dotenv

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()

# -----------------------------
# Databricks connection config
# -----------------------------
SERVER_HOSTNAME = os.getenv("DATABRICKS_SERVER_HOSTNAME")
HTTP_PATH       = os.getenv("DATABRICKS_HTTP_PATH")
TOKEN           = os.getenv("DATABRICKS_TOKEN")
CATALOG         = os.getenv("CATALOG", "demo_catalog")
SCHEMA          = os.getenv("SCHEMA", "demo_schema")

st.set_page_config(page_title="[PoC] Crypto Insight Dashboard (Live)", layout="wide")
st.title("[PoC] Crypto Insight Dashboard (Live via Databricks SQL)")

# Quick sanity check for required envs
missing = [k for k, v in {
    "DATABRICKS_SERVER_HOSTNAME": SERVER_HOSTNAME,
    "DATABRICKS_HTTP_PATH": HTTP_PATH,
    "DATABRICKS_TOKEN": TOKEN
}.items() if not v]
if missing:
    st.error(f"Missing environment variables: {', '.join(missing)}")
    st.stop()

# -----------------------------
# Helper: run a SQL query and return DataFrame
# Uses DB-API parameter binding with `?`
# -----------------------------
def run_query(query: str, params: tuple | None = None) -> pd.DataFrame:
    with sql.connect(server_hostname=SERVER_HOSTNAME, http_path=HTTP_PATH, access_token=TOKEN) as conn:
        with conn.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

# -----------------------------
# Cached query wrappers (TTL controls frequency → cost/latency tradeoff)
# Each query is already filtered by symbol at the SQL level
# -----------------------------
@st.cache_data(ttl=60, show_spinner=False)
def q_distinct_symbols() -> list[str]:
    q = f"SELECT DISTINCT symbol FROM {CATALOG}.{SCHEMA}.v_latest_price"
    df = run_query(q)
    return sorted(df["symbol"].tolist())

@st.cache_data(ttl=60, show_spinner=False)
def q_latest_price_sym(symbol: str) -> pd.DataFrame:
    q = f"""
    SELECT symbol, last_price, last_ts
    FROM {CATALOG}.{SCHEMA}.v_latest_price
    WHERE symbol = ?
    """
    return run_query(q, (symbol,))

@st.cache_data(ttl=60, show_spinner=False)
def q_summary_24h_sym(symbol: str) -> pd.DataFrame:
    q = f"""
    SELECT symbol, last_price, avg_price_24h, abs_change_24h, pct_change_24h
    FROM {CATALOG}.{SCHEMA}.v_summary_24h
    WHERE symbol = ?
    """
    return run_query(q, (symbol,))

@st.cache_data(ttl=60, show_spinner=False)
def q_signal_latest_sym(symbol: str) -> pd.DataFrame:
    q = f"""
    WITH ranked AS (
      SELECT symbol, cross_signal, above_ma200, bucket_start,
             ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY bucket_start DESC) rn
      FROM {CATALOG}.{SCHEMA}.v_signals
      WHERE symbol = ?
    )
    SELECT symbol, cross_signal, above_ma200, bucket_start
    FROM ranked WHERE rn = 1
    """
    return run_query(q, (symbol,))

@st.cache_data(ttl=60, show_spinner=False)
def q_series_sym(symbol: str, hours_back: int) -> pd.DataFrame:
    # Restrict time window to reduce data scanned and cost
    q = f"""
    SELECT symbol, bucket_start AS ts, avg_price, ma_50, ma_200
    FROM {CATALOG}.{SCHEMA}.v_signals
    WHERE symbol = ?
      AND bucket_start >= now() - INTERVAL {{hours}} HOURS
    ORDER BY ts
    """
    return run_query(q.replace("{hours}", str(hours_back)), (symbol,))

# -----------------------------
# Sidebar controls (single-select)
# -----------------------------
symbols = q_distinct_symbols()
if not symbols:
    st.info("No symbols available.")
    st.stop()

sel_symbol = st.sidebar.selectbox("Symbol", options=symbols, index=0)
hours_back = st.sidebar.slider("Lookback (hours)", 6, 96, 48)

# -----------------------------
# Load data for selected symbol
# -----------------------------
latest_df  = q_latest_price_sym(sel_symbol)
summary_df = q_summary_24h_sym(sel_symbol)
signal_df  = q_signal_latest_sym(sel_symbol)
series_df  = q_series_sym(sel_symbol, hours_back)

# -----------------------------
# KPI section
# -----------------------------
col1, col2, col3 = st.columns(3)

# Latest Price KPI
kpi_price, kpi_time = np.nan, None
if not latest_df.empty:
    kpi_price = float(latest_df["last_price"].iloc[0])
    kpi_time  = latest_df["last_ts"].iloc[0]

with col1:
    st.caption("Latest Price")
    st.metric(label=sel_symbol, value=f"{kpi_price:,.2f}" if np.isfinite(kpi_price) else "-")
    if kpi_time is not None:
        st.caption(f"Updated: {kpi_time}")

# 24h Change % KPI
kpi_change = np.nan
if not summary_df.empty:
    kpi_change = float(summary_df["pct_change_24h"].iloc[0])

with col2:
    st.caption("24h Change %")
    st.metric(label=sel_symbol, value=f"{kpi_change:.2f}" if np.isfinite(kpi_change) else "-")

# Cross Signal KPI
kpi_signal = signal_df["cross_signal"].iloc[0] if not signal_df.empty else "-"
with col3:
    st.caption("Cross Signal")
    st.header(kpi_signal)

st.divider()

# -----------------------------
# Price Trends (line chart)
# -----------------------------
st.subheader("Price Trends")
if series_df.empty:
    st.info("No data in the selected time window.")
else:
    melted = series_df.melt(
        id_vars=["ts", "symbol"],
        value_vars=["avg_price", "ma_50", "ma_200"],
        var_name="series", value_name="value"
    )
    fig = px.line(melted, x="ts", y="value", color="series", hover_data=["symbol"])
    fig.update_layout(height=420, legend_title_text="")
    st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# Signal Summary (single symbol)
# -----------------------------
st.subheader("Signal Summary")
if signal_df.empty:
    st.info("No signal rows.")
else:
    st.dataframe(signal_df, use_container_width=True, hide_index=True)

# -----------------------------
# 24h Summary (single symbol)
# -----------------------------
st.subheader("24h Summary")
if summary_df.empty:
    st.info("No summary rows.")
else:
    tmp = summary_df.copy()
    tmp["pct_change_24h"] = tmp["pct_change_24h"].round(2)
    st.dataframe(tmp, use_container_width=True, hide_index=True)

# -----------------------------
# Manual refresh to invalidate caches
# -----------------------------
if st.sidebar.button("Refresh now"):
    q_distinct_symbols.clear()
    q_latest_price_sym.clear()
    q_summary_24h_sym.clear()
    q_signal_latest_sym.clear()
    q_series_sym.clear()
    st.rerun()