# ITH Strategy Dashboard

Streamlit dashboard for checking Eon-style ITH metrics from a strategy NAV CSV.

## Files

- `app.py` - Streamlit app entry point.
- `ith_evaluator.py` - ITH, TMAEG, drawdown, and trade-frequency calculations.
- `requirements.txt` - Python dependencies for Streamlit Cloud.

## Deploy

Use this as the Streamlit main file path:

```text
app.py
```

Do not push exchange API keys or private credentials.

## Expected NAV CSV

The app expects a CSV with:

```text
Date,NAV
01/11/2021,1.0
02/11/2021,1.01
```

Optional trades CSV can contain:

```text
entry_time
2022-01-22 21:36:00
```

The large ETH 1-minute data file should stay local unless you intentionally use Git LFS or private object storage.
