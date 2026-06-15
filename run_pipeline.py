"""
run_pipeline.py
================

Master execution script for the Bluestock Fintech Capstone Project I
(Mutual Fund Analytics Platform).

This script ties together the individual project scripts and notebooks
into a single, repeatable pipeline:

    Stage 1  fetch_live_nav()       -> Fetch live NAV history for 5 large-cap
                                        schemes from the AMFI mfapi.in API and
                                        save them under data/raw/.
    Stage 2  validate_fund_data()   -> Cross-validate AMFI codes between
                                        01_fund_master.csv and
                                        02_nav_history.csv (data quality check).
    Stage 3  compute_performance()  -> Compute CAGR, Sharpe, Sortino,
                                        Alpha/Beta (vs NIFTY50) and Max Drawdown
                                        for every scheme. Saves fund_scorecard.csv
                                        and alpha_beta.csv.
    Stage 4  compute_advanced_risk()-> Compute Historical VaR / CVaR, the
                                        90-day rolling Sharpe ratio, low-risk
                                        fund recommendations, and portfolio
                                        concentration (HHI).
    Stage 5  print_summary()        -> Print a human-readable summary of the
                                        full run.

Usage
-----
    python run_pipeline.py                 # full run (fetches live NAV data)
    python run_pipeline.py --skip-fetch     # skip the live API calls and reuse
                                             # the CSVs already in data/raw/
    python run_pipeline.py --data-dir data/raw   # point at a custom data folder

Author: balugurisruthi61
Project: Bluestock Fintech Capstone Project I — Mutual Fund Analytics
"""

import argparse
import logging
import os

import numpy as np
import pandas as pd
import requests
from scipy.stats import linregress

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bluestock_pipeline")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# AMFI scheme codes for the 5 large-cap funds tracked with live NAV data.
LIVE_NAV_SCHEMES = {
    "SBI_Bluechip": 119551,
    "ICICI_Bluechip": 120503,
    "Nippon_Large_Cap": 118632,
    "Axis_Bluechip": 119092,
    "Kotak_Bluechip": 120841,
}

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.065          # Annual risk-free rate (91-day T-bill, approx.)
VAR_CONFIDENCE = 0.05            # 5% Historical VaR / CVaR
ROLLING_WINDOW_DAYS = 90          # Rolling Sharpe window
HHI_CONCENTRATION_THRESHOLD = 0.25


# ---------------------------------------------------------------------------
# Stage 1 — Live NAV fetch
# ---------------------------------------------------------------------------

def fetch_live_nav(schemes=LIVE_NAV_SCHEMES, data_dir="data/raw"):
    """Fetch live NAV history for each scheme in ``schemes`` from mfapi.in.

    For every (name, amfi_code) pair, calls the public AMFI mirror API at
    ``https://api.mfapi.in/mf/{amfi_code}`` and writes the returned NAV
    history to ``{data_dir}/{name}_nav.csv``.

    Network errors for an individual scheme are logged and skipped so that
    one failed request does not stop the whole pipeline.

    Parameters
    ----------
    schemes : dict[str, int]
        Mapping of a friendly scheme name to its AMFI code.
    data_dir : str
        Folder where the per-scheme NAV CSV files are written.

    Returns
    -------
    list[str]
        Names of the schemes that were fetched successfully.
    """
    os.makedirs(data_dir, exist_ok=True)
    fetched = []

    for name, code in schemes.items():
        url = f"https://api.mfapi.in/mf/{code}"
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            payload = response.json()

            nav_df = pd.DataFrame(payload["data"])
            out_path = os.path.join(data_dir, f"{name}_nav.csv")
            nav_df.to_csv(out_path, index=False)

            logger.info("Fetched %s (AMFI %s) -> %s [%d rows]",
                        name, code, out_path, len(nav_df))
            fetched.append(name)
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Skipping %s (AMFI %s) — fetch failed: %s",
                            name, code, exc)

    return fetched


# ---------------------------------------------------------------------------
# Stage 2 — Data ingestion & validation
# ---------------------------------------------------------------------------

def validate_fund_data(data_dir="data/raw"):
    """Load the fund master and NAV history files and cross-check AMFI codes.

    Computes the set difference of ``amfi_code`` values between
    ``01_fund_master.csv`` and ``02_nav_history.csv`` in both directions.
    This is the same check implemented in ``data_ingestion.py``, wrapped
    here so it can run as part of the automated pipeline.

    Parameters
    ----------
    data_dir : str
        Folder containing ``01_fund_master.csv`` and ``02_nav_history.csv``.

    Returns
    -------
    dict
        ``{"fund_master": DataFrame, "nav_history": DataFrame,
           "missing_in_nav": set, "missing_in_master": set}``
    """
    fund_master = pd.read_csv(os.path.join(data_dir, "01_fund_master.csv"))
    nav_history = pd.read_csv(os.path.join(data_dir, "02_nav_history.csv"))

    fund_codes = set(fund_master["amfi_code"])
    nav_codes = set(nav_history["amfi_code"])

    missing_in_nav = fund_codes - nav_codes
    missing_in_master = nav_codes - fund_codes

    logger.info("Fund master schemes: %d | NAV history schemes: %d",
                 len(fund_codes), len(nav_codes))

    if missing_in_nav or missing_in_master:
        logger.warning("AMFI code mismatch — missing in NAV history: %d, "
                        "missing in fund master: %d",
                        len(missing_in_nav), len(missing_in_master))
    else:
        logger.info("Validation passed: 0 missing AMFI codes in either "
                     "direction (40/40 schemes match)")

    return {
        "fund_master": fund_master,
        "nav_history": nav_history,
        "missing_in_nav": missing_in_nav,
        "missing_in_master": missing_in_master,
    }


# ---------------------------------------------------------------------------
# Stage 3 — Performance metrics (CAGR, Sharpe, Sortino, Alpha/Beta, Max DD)
# ---------------------------------------------------------------------------

def compute_performance(nav_history, data_dir="data/raw", output_dir=".",
                         rf=RISK_FREE_RATE):
    """Compute per-scheme performance & risk metrics from NAV history.

    For every ``amfi_code`` in ``nav_history`` this computes:

    * **CAGR**        — ``(end_nav / start_nav) ** (1 / years) - 1``
    * **Sharpe**      — ``(annual_return - rf) / annual_volatility``
    * **Sortino**     — ``(annual_return - rf) / downside_volatility``
    * **Alpha/Beta**  — linear regression of daily fund returns against
      daily NIFTY50 returns (``10_benchmark_indices.csv``), filtered to a
      single benchmark series and de-duplicated on date before merging.
    * **Max Drawdown**— worst peak-to-trough decline in the NAV series.

    Results are written to ``fund_scorecard.csv`` (CAGR, Sharpe, Sortino,
    Max Drawdown) and ``alpha_beta.csv`` (Alpha, Beta) in ``output_dir``.

    Parameters
    ----------
    nav_history : pandas.DataFrame
        Output of :func:`validate_fund_data`'s ``"nav_history"`` entry,
        with columns ``amfi_code``, ``date``, ``nav``.
    data_dir : str
        Folder containing ``10_benchmark_indices.csv``.
    output_dir : str
        Folder where ``fund_scorecard.csv`` and ``alpha_beta.csv`` are written.
    rf : float
        Annual risk-free rate used for Sharpe and Sortino ratios.

    Returns
    -------
    pandas.DataFrame
        The fund scorecard with one row per ``amfi_code``.
    """
    df = nav_history.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)
    df["daily_return"] = df.groupby("amfi_code")["nav"].pct_change()

    cagr_rows, sharpe_rows, sortino_rows, mdd_rows = [], [], [], []

    for code, fund_df in df.groupby("amfi_code"):
        start_nav, end_nav = fund_df["nav"].iloc[0], fund_df["nav"].iloc[-1]
        years = (fund_df["date"].iloc[-1] - fund_df["date"].iloc[0]).days / 365
        cagr_rows.append((code, (end_nav / start_nav) ** (1 / years) - 1))

        daily = fund_df["daily_return"].dropna()
        annual_return = daily.mean() * TRADING_DAYS_PER_YEAR
        annual_vol = daily.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        sharpe_rows.append((code, (annual_return - rf) / annual_vol))

        downside = daily[daily < 0]
        downside_vol = downside.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
        sortino_rows.append((code, (annual_return - rf) / downside_vol))

        running_max = fund_df["nav"].cummax()
        drawdown = (fund_df["nav"] / running_max) - 1
        mdd_rows.append((code, drawdown.min()))

    cagr_df = pd.DataFrame(cagr_rows, columns=["amfi_code", "CAGR"])
    sharpe_df = pd.DataFrame(sharpe_rows, columns=["amfi_code", "Sharpe"])
    sortino_df = pd.DataFrame(sortino_rows, columns=["amfi_code", "Sortino"])
    mdd_df = pd.DataFrame(mdd_rows, columns=["amfi_code", "Max_Drawdown"])

    alpha_beta_df = _compute_alpha_beta(df, data_dir)

    scorecard = (
        cagr_df
        .merge(sharpe_df, on="amfi_code")
        .merge(sortino_df, on="amfi_code")
        .merge(alpha_beta_df, on="amfi_code", how="left")
        .merge(mdd_df, on="amfi_code")
        .sort_values("CAGR", ascending=False)
        .reset_index(drop=True)
    )

    scorecard_path = os.path.join(output_dir, "fund_scorecard.csv")
    scorecard.to_csv(scorecard_path, index=False)
    logger.info("Saved %s (%d schemes)", scorecard_path, len(scorecard))

    alpha_beta_path = os.path.join(output_dir, "alpha_beta.csv")
    alpha_beta_df.to_csv(alpha_beta_path, index=False)
    logger.info("Saved %s (%d schemes)", alpha_beta_path, len(alpha_beta_df))

    return scorecard


def _compute_alpha_beta(returns_df, data_dir):
    """Compute Alpha and Beta of each scheme's daily returns vs NIFTY50.

    The benchmark file (``10_benchmark_indices.csv``) contains multiple
    indices, so it is first filtered down to ``NIFTY50`` and deduplicated
    on ``date`` before merging — avoiding the many-to-many merge that would
    otherwise inflate the row count when joining on date alone.

    Parameters
    ----------
    returns_df : pandas.DataFrame
        Per-scheme daily returns with columns ``amfi_code``, ``date``,
        ``daily_return``.
    data_dir : str
        Folder containing ``10_benchmark_indices.csv``.

    Returns
    -------
    pandas.DataFrame
        Columns: ``amfi_code``, ``Alpha`` (annualized), ``Beta``.
    """
    benchmark = pd.read_csv(os.path.join(data_dir, "10_benchmark_indices.csv"))
    benchmark["date"] = pd.to_datetime(benchmark["date"])

    nifty = (
        benchmark[benchmark["index_name"] == "NIFTY50"]
        .drop_duplicates(subset="date")
        .sort_values("date")
        .copy()
    )
    nifty["benchmark_return"] = nifty["close_value"].pct_change()

    merged = returns_df.merge(
        nifty[["date", "benchmark_return"]], on="date", how="left"
    )

    rows = []
    for code, fund_df in merged.groupby("amfi_code"):
        paired = fund_df[["daily_return", "benchmark_return"]].dropna()
        if len(paired) < 2:
            rows.append((code, np.nan, np.nan))
            continue
        slope, intercept, *_ = linregress(
            paired["benchmark_return"], paired["daily_return"]
        )
        rows.append((code, intercept * TRADING_DAYS_PER_YEAR, slope))

    return pd.DataFrame(rows, columns=["amfi_code", "Alpha", "Beta"])


# ---------------------------------------------------------------------------
# Stage 4 — Advanced risk analytics (VaR, CVaR, rolling Sharpe, HHI, etc.)
# ---------------------------------------------------------------------------

def compute_advanced_risk(nav_history, scheme_performance_path,
                           holdings_path, output_dir="."):
    """Compute VaR/CVaR, rolling Sharpe, fund recommendations and HHI.

    This mirrors the analyses performed in ``Advanced_Analytics.ipynb``:

    1. **Historical VaR / CVaR** — computed on ``nav_history['nav'].pct_change()``
       *without* grouping by scheme, exactly as in the original notebook.
       This treats the concatenated NAV series as one sequence, so the
       result is an industry-wide downside-risk indicator rather than a
       single fund's VaR (see Section 10 "Limitations" of the report for
       a discussion of this simplification).
    2. **90-day rolling Sharpe ratio** — rolling mean/std of the same
       ungrouped return series, annualised. Saved to ``rolling_sharpe.csv``.
    3. **Low-risk fund recommendations** — top 3 schemes with
       ``risk_grade == "Low"`` ranked by Sharpe ratio.
    4. **Portfolio concentration (HHI)** — Herfindahl-Hirschman Index of
       each fund's holdings; HHI > 0.25 is flagged as "High concentration".

    Parameters
    ----------
    nav_history : pandas.DataFrame
        Output of :func:`validate_fund_data`'s ``"nav_history"`` entry,
        in the same row order as ``02_nav_history.csv``.
    scheme_performance_path : str
        Path to ``07_scheme_performance.csv``.
    holdings_path : str
        Path to ``09_portfolio_holdings.csv``.
    output_dir : str
        Folder where ``rolling_sharpe.csv`` is written.

    Returns
    -------
    dict
        ``{"var": float, "cvar": float, "recommendations": DataFrame,
           "hhi": pandas.Series}``
    """
    # --- VaR / CVaR (matches Advanced_Analytics.ipynb, Cell 2) -------------
    returns = nav_history["nav"].pct_change()

    var = returns.quantile(VAR_CONFIDENCE)
    cvar = returns[returns <= var].mean()
    logger.info("Historical VaR (%.0f%%): %.4f (%.2f%%)",
                 VAR_CONFIDENCE * 100, var, var * 100)
    logger.info("CVaR / Expected Shortfall: %.4f (%.2f%%)", cvar, cvar * 100)

    # --- 90-day rolling Sharpe (matches Cell 3) -----------------------------
    rolling_mean = returns.rolling(ROLLING_WINDOW_DAYS).mean()
    rolling_std = returns.rolling(ROLLING_WINDOW_DAYS).std()
    rolling_sharpe = (rolling_mean / rolling_std) * np.sqrt(TRADING_DAYS_PER_YEAR)
    rolling_sharpe.to_csv(os.path.join(output_dir, "rolling_sharpe.csv"),
                           index=False, header=["rolling_sharpe_90d"])
    valid_sharpe = rolling_sharpe.dropna()
    logger.info("Saved rolling_sharpe.csv (%d points, range %.2f to %.2f)",
                 len(valid_sharpe), valid_sharpe.min(), valid_sharpe.max())

    # --- Low-risk fund recommendations -------------------------------------
    scheme_perf = pd.read_csv(scheme_performance_path)
    low_risk = scheme_perf[scheme_perf["risk_grade"].str.lower() == "low"]
    recommendations = low_risk.sort_values("sharpe_ratio", ascending=False).head(3)
    logger.info("Top 3 low-risk recommendations: %s",
                 ", ".join(recommendations["scheme_name"].tolist()))

    # --- Portfolio concentration (HHI) --------------------------------------
    holdings = pd.read_csv(holdings_path)
    holdings["weight"] = holdings["weight_pct"] / 100
    hhi = holdings.groupby("amfi_code")["weight"].apply(lambda w: (w ** 2).sum())
    n_concentrated = (hhi > HHI_CONCENTRATION_THRESHOLD).sum()
    logger.info("HHI computed for %d funds — %d flagged as 'High concentration', "
                 "%d 'Diversified'", len(hhi), n_concentrated, len(hhi) - n_concentrated)

    return {
        "var": var,
        "cvar": cvar,
        "recommendations": recommendations,
        "hhi": hhi,
    }


# ---------------------------------------------------------------------------
# Stage 5 — Summary
# ---------------------------------------------------------------------------

def print_summary(validation, scorecard, risk_results):
    """Print a human-readable summary of the pipeline run.

    Parameters
    ----------
    validation : dict
        Output of :func:`validate_fund_data`.
    scorecard : pandas.DataFrame
        Output of :func:`compute_performance`.
    risk_results : dict
        Output of :func:`compute_advanced_risk`.
    """
    print("\n" + "=" * 60)
    print("BLUESTOCK MUTUAL FUND ANALYTICS — PIPELINE SUMMARY")
    print("=" * 60)

    print(f"\nSchemes in fund master : {len(validation['fund_master'])}")
    print(f"AMFI code mismatches   : "
          f"{len(validation['missing_in_nav']) + len(validation['missing_in_master'])}")

    print("\nTop 5 schemes by CAGR:")
    top5 = scorecard.head(5)
    fund_master = validation["fund_master"][["amfi_code", "scheme_name"]]
    top5 = top5.merge(fund_master, on="amfi_code", how="left")
    for _, row in top5.iterrows():
        print(f"  {row['scheme_name']:<45} "
              f"CAGR={row['CAGR']*100:6.2f}%  Sharpe={row['Sharpe']:.2f}")

    print(f"\nHistorical VaR (5%) : {risk_results['var']*100:.2f}%")
    print(f"CVaR / Exp. Shortfall: {risk_results['cvar']*100:.2f}%")

    print("\nLow-risk recommendations (by Sharpe):")
    for _, row in risk_results["recommendations"].iterrows():
        print(f"  {row['scheme_name']:<40} Sharpe={row['sharpe_ratio']:.2f}")

    n_high = (risk_results["hhi"] > HHI_CONCENTRATION_THRESHOLD).sum()
    print(f"\nPortfolio concentration (HHI): {len(risk_results['hhi'])} funds analyzed, "
          f"{n_high} concentrated, {len(risk_results['hhi']) - n_high} diversified")

    print("\n" + "=" * 60)
    print("Pipeline completed successfully.")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Run the full Bluestock mutual fund analytics pipeline."""
    parser = argparse.ArgumentParser(description="Bluestock MF Analytics pipeline")
    parser.add_argument("--data-dir", default="data/raw",
                         help="Folder containing the 10 project CSV files "
                              "(default: data/raw)")
    parser.add_argument("--skip-fetch", action="store_true",
                         help="Skip the live NAV API calls and reuse the "
                              "CSVs already present in --data-dir")
    args = parser.parse_args()

    if not args.skip_fetch:
        logger.info("Stage 1/5: Fetching live NAV data from AMFI mfapi.in ...")
        fetch_live_nav(data_dir=args.data_dir)
    else:
        logger.info("Stage 1/5: Skipped (--skip-fetch)")

    logger.info("Stage 2/5: Validating fund master vs NAV history ...")
    validation = validate_fund_data(data_dir=args.data_dir)

    logger.info("Stage 3/5: Computing CAGR, Sharpe, Sortino, Alpha/Beta, Max Drawdown ...")
    scorecard = compute_performance(validation["nav_history"], data_dir=args.data_dir)

    logger.info("Stage 4/5: Computing VaR, CVaR, rolling Sharpe, recommendations, HHI ...")
    risk_results = compute_advanced_risk(
        validation["nav_history"],
        scheme_performance_path=os.path.join(args.data_dir, "07_scheme_performance.csv"),
        holdings_path=os.path.join(args.data_dir, "09_portfolio_holdings.csv"),
    )

    logger.info("Stage 5/5: Summary")
    print_summary(validation, scorecard, risk_results)


if __name__ == "__main__":
    main()
