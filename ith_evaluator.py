from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IthResult:
    tmaeg: float
    max_drawdown: float
    num_epochs: int
    d2ithe: float | None
    days_elapsed: int
    epoch_dates: list[pd.Timestamp]
    calculated: pd.DataFrame


@dataclass(frozen=True)
class TradeFrequencyResult:
    total_trades: int
    trades_per_day: float
    max_rolling_28d_trades: int


def max_drawdown(nav: pd.Series) -> float:
    nav = nav.astype(float)
    return float((1.0 - nav / nav.cummax()).max())


def calculate_excess_gain_loss(nav_df: pd.DataFrame, hurdle: float) -> pd.DataFrame:
    nav = nav_df["NAV"].astype(float).to_numpy()
    if len(nav) < 2:
        raise ValueError("NAV series must have at least two rows.")

    excess_gain = 0.0
    excess_loss = 0.0
    excess_gains = [0.0]
    excess_losses = [0.0]
    ith_epochs = [False] * len(nav)

    endorsing_crest = nav[0]
    candidate_crest = nav[0]
    candidate_nadir = nav[0]

    for i, (equity, next_equity) in enumerate(zip(nav[:-1], nav[1:])):
        if next_equity > candidate_crest:
            excess_gain = next_equity / endorsing_crest - 1.0 if endorsing_crest != 0 else 0.0
            candidate_crest = next_equity

        if next_equity < candidate_nadir:
            excess_loss = 1.0 - next_equity / endorsing_crest if endorsing_crest != 0 else 0.0
            candidate_nadir = next_equity

        reset = (
            excess_gain > abs(excess_loss)
            and excess_gain > hurdle
            and candidate_crest >= endorsing_crest
        )

        if reset:
            endorsing_crest = candidate_crest
            candidate_nadir = equity

        excess_gains.append(excess_gain)
        excess_losses.append(excess_loss)

        if reset:
            excess_gain = 0.0
            excess_loss = 0.0

        ith_epochs[i + 1] = (
            len(excess_gains) > 1
            and excess_gains[-1] > excess_losses[-1]
            and excess_gains[-1] > hurdle
        )

    out = nav_df.copy()
    out["Excess Gains"] = excess_gains
    out["Excess Losses"] = excess_losses
    out["ITHEs"] = ith_epochs
    return out


def evaluate_ith(nav_df: pd.DataFrame, tmaeg_mode: str = "mdd", fixed_tmaeg: float = 0.01) -> IthResult:
    if "NAV" not in nav_df.columns:
        raise ValueError("NAV dataframe must contain a NAV column.")

    nav_df = nav_df.copy().sort_index()
    nav_df["NAV"] = pd.to_numeric(nav_df["NAV"], errors="coerce")
    nav_df = nav_df.dropna(subset=["NAV"])

    mdd = max_drawdown(nav_df["NAV"])
    if tmaeg_mode == "mdd":
        tmaeg = mdd
    elif tmaeg_mode == "fixed":
        tmaeg = float(fixed_tmaeg)
    else:
        raise ValueError("tmaeg_mode must be 'mdd' or 'fixed'.")

    calculated = calculate_excess_gain_loss(nav_df, tmaeg)
    epoch_dates = list(calculated.index[calculated["ITHEs"]])
    days_elapsed = len(calculated.resample("D").last())
    d2ithe = None if not epoch_dates else days_elapsed / len(epoch_dates)

    return IthResult(
        tmaeg=tmaeg,
        max_drawdown=mdd,
        num_epochs=len(epoch_dates),
        d2ithe=d2ithe,
        days_elapsed=days_elapsed,
        epoch_dates=epoch_dates,
        calculated=calculated,
    )


def evaluate_trade_frequency(trades_df: pd.DataFrame) -> TradeFrequencyResult:
    cols = {c.lower().strip(): c for c in trades_df.columns}
    time_col = cols.get("entry_time") or cols.get("date") or cols.get("timestamp")
    if time_col is None:
        raise ValueError("Trades CSV must contain entry_time, Date, or timestamp column.")

    times = pd.to_datetime(trades_df[time_col], errors="coerce")
    times = times.dropna().sort_values()
    if times.empty:
        return TradeFrequencyResult(total_trades=0, trades_per_day=0.0, max_rolling_28d_trades=0)

    span_days = max((times.iloc[-1] - times.iloc[0]).total_seconds() / 86400.0, 1.0)
    trades_per_day = len(times) / span_days

    daily_counts = pd.Series(1, index=times).resample("D").sum().fillna(0)
    rolling_28d = daily_counts.rolling(28, min_periods=1).sum()

    return TradeFrequencyResult(
        total_trades=int(len(times)),
        trades_per_day=float(trades_per_day),
        max_rolling_28d_trades=int(rolling_28d.max()),
    )
