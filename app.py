from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ith_evaluator import evaluate_ith, evaluate_trade_frequency


st.set_page_config(page_title="ITH Strategy Dashboard", layout="wide")

st.title("ITH Strategy Dashboard")

with st.sidebar:
    st.header("Inputs")
    initial_capital = st.number_input("Initial capital", min_value=1_000.0, value=100_000.0, step=10_000.0)
    ith_target_days = st.number_input("ITH target days", min_value=1, value=28, step=1)
    tmaeg_mode = st.selectbox("TMAEG mode", ["mdd", "fixed"], index=0)
    fixed_tmaeg = st.number_input("Fixed TMAEG %", min_value=0.01, value=1.0, step=0.1) / 100.0

    st.divider()
    nav_upload = st.file_uploader("Upload NAV CSV", type=["csv"])
    trades_upload = st.file_uploader("Upload trades CSV optional", type=["csv"])


def load_csv(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    return pd.read_csv(io.BytesIO(raw))


def normalize_nav(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower().strip(): c for c in df.columns}
    if "date" not in cols or "nav" not in cols:
        raise ValueError("NAV CSV must contain Date and NAV columns.")

    out = df[[cols["date"], cols["nav"]]].copy()
    out.columns = ["Date", "NAV"]
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", dayfirst=True)
    out["NAV"] = pd.to_numeric(out["NAV"], errors="coerce")
    out = out.dropna(subset=["Date", "NAV"]).sort_values("Date")

    if out.empty:
        raise ValueError("NAV CSV has no valid Date/NAV rows.")

    out = out.drop_duplicates(subset=["Date"], keep="last").set_index("Date")
    if out["NAV"].iloc[0] != 0:
        out["Capital"] = out["NAV"] / out["NAV"].iloc[0] * initial_capital
    else:
        out["Capital"] = out["NAV"]
    return out


def nav_chart(nav: pd.DataFrame, result) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=nav.index, y=nav["Capital"], name="Capital", mode="lines"))
    if result.epoch_dates:
        epoch_nav = nav.loc[result.epoch_dates, "Capital"]
        fig.add_trace(
            go.Scatter(
                x=epoch_nav.index,
                y=epoch_nav.values,
                name="ITH epochs",
                mode="markers",
                marker={"size": 10},
            )
        )
    fig.update_layout(height=420, margin={"l": 20, "r": 20, "t": 30, "b": 20})
    return fig


def excess_chart(result) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result.calculated.index, y=result.calculated["Excess Gains"] * 100, name="Excess gain %"))
    fig.add_trace(go.Scatter(x=result.calculated.index, y=result.calculated["Excess Losses"] * 100, name="Excess loss %"))
    fig.add_hline(y=result.tmaeg * 100, line_dash="dash", annotation_text="TMAEG")
    fig.update_layout(height=360, margin={"l": 20, "r": 20, "t": 30, "b": 20})
    return fig


def drawdown_chart(nav: pd.DataFrame) -> go.Figure:
    dd = 1.0 - nav["NAV"] / nav["NAV"].cummax()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dd.index, y=dd * 100, name="Drawdown %", mode="lines"))
    fig.update_layout(height=300, margin={"l": 20, "r": 20, "t": 30, "b": 20})
    return fig


if nav_upload is None:
    st.info("Upload a daily NAV CSV with Date and NAV columns. Do not upload private API keys or exchange credentials.")
    st.stop()

try:
    nav_df = normalize_nav(load_csv(nav_upload))
    result = evaluate_ith(nav_df[["NAV"]], tmaeg_mode=tmaeg_mode, fixed_tmaeg=fixed_tmaeg)
except Exception as exc:
    st.error(str(exc))
    st.stop()

required_epochs = int((result.days_elapsed + ith_target_days - 1) // ith_target_days)
passes_ith = result.d2ithe is not None and result.d2ithe < ith_target_days

metric_cols = st.columns(6)
metric_cols[0].metric("Initial capital", f"${initial_capital:,.0f}")
metric_cols[1].metric("Final capital", f"${nav_df['Capital'].iloc[-1]:,.2f}")
metric_cols[2].metric("TMAEG", f"{result.tmaeg * 100:.3f}%")
metric_cols[3].metric("Max DD", f"{result.max_drawdown * 100:.3f}%")
metric_cols[4].metric("ITH epochs", f"{result.num_epochs} / {required_epochs}")
metric_cols[5].metric("D2ITHE", "N/A" if result.d2ithe is None else f"{result.d2ithe:.2f} days")

if passes_ith:
    st.success(f"ITH target passed: D2ITHE is below {ith_target_days} days.")
else:
    st.warning(f"ITH target not passed yet. Need D2ITHE below {ith_target_days} days.")

tab_nav, tab_excess, tab_dd, tab_trades, tab_data = st.tabs(["NAV", "Excess", "Drawdown", "Trades", "Data"])

with tab_nav:
    st.plotly_chart(nav_chart(nav_df, result), use_container_width=True)

with tab_excess:
    st.plotly_chart(excess_chart(result), use_container_width=True)

with tab_dd:
    st.plotly_chart(drawdown_chart(nav_df), use_container_width=True)

with tab_trades:
    if trades_upload is None:
        st.info("Upload backtest_trades.csv to calculate trades/day and rolling 28-day MRTF.")
    else:
        try:
            trades_df = load_csv(trades_upload)
            freq = evaluate_trade_frequency(trades_df)
            cols = st.columns(3)
            cols[0].metric("Total trades", f"{freq.total_trades:,}")
            cols[1].metric("Trades/day", f"{freq.trades_per_day:.2f}")
            cols[2].metric("Max 28d MRTF", f"{freq.max_rolling_28d_trades:,}")
            st.dataframe(trades_df.head(500), use_container_width=True)
        except Exception as exc:
            st.error(str(exc))

with tab_data:
    st.subheader("ITH epoch dates")
    st.dataframe(pd.DataFrame({"Date": result.epoch_dates}), use_container_width=True)
    st.subheader("Calculated NAV")
    st.dataframe(result.calculated.tail(500), use_container_width=True)
