# Crypto Insight Dashboard (Live via Databricks SQL)

This project provides a local Streamlit dashboard that connects to **Databricks SQL**  
and visualizes cryptocurrency market signals (price, moving averages, cross signals).

It assumes that required Delta tables and views already exist in Databricks:
- `demo_catalog.demo_schema.v_latest_price`
- `demo_catalog.demo_schema.v_summary_24h`
- `demo_catalog.demo_schema.v_signals`

---

## 1. Prerequisites

- Python
- A Databricks workspace with:
  - SQL Warehouse
  - Personal Access Token
  - The views listed above created and populated

---

## 2. Setup

Clone the repository and move into the folder:

```bash
git clone https://github.com/your-username/crypto_dashboard_live.git
cd crypto_dashboard_live
```

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Configuration

Create a `.env` file in the project root:

```ini
DATABRICKS_SERVER_HOSTNAME=dbc-xxxxxxxxx-de1a.cloud.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/xxxxxx
DATABRICKS_TOKEN=dapiXXXXXXXXXXXXXX
CATALOG=demo_catalog
SCHEMA=demo_schema
```

Values for `SERVER_HOSTNAME`, `HTTP_PATH`, and `TOKEN` can be found in the Databricks console  
under **SQL Warehouses → [your warehouse] → Connection details**.

---

## 4. Run the dashboard

Start the Streamlit app:

```bash
streamlit run app.py
```

Then open the URL shown in the terminal: [http://localhost:8501](http://localhost:8501).

---

## 5. Usage

- Select a symbol from the sidebar (e.g. `BTCUSDT`).
- The dashboard will display:
  - **KPIs**: Latest Price, 24h Change %, Cross Signal
  - **Price Trends**: Line chart with Avg Price, MA50, MA200
  - **Signal Summary**: Latest cross/MA200 signal
  - **24h Summary**: Price change statistics
- Use **Refresh now** in the sidebar to clear cache and fetch fresh data.

---

## 6. Cost considerations

- Queries are executed only while the Streamlit app is running.  
- Each query result is cached for 60 seconds to avoid excessive calls.
