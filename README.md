# Mutual Fund Analytics Platform

**Bluestock Fintech Capstone Project I — Individual Submission**
Cohort: MJ28 · Author: [balugurisruthi61](https://github.com/balugurisruthi61-bot) · June 2026

An end-to-end data analytics pipeline for Indian mutual funds — covering
live NAV ingestion, data validation, exploratory data analysis, performance
& risk metrics (CAGR, Sharpe, Sortino, Alpha/Beta, Max Drawdown, VaR, CVaR),
fund recommendations, portfolio concentration analysis, and a Power BI
dashboard for investor transaction analytics.

---

## 1. Project Overview

| | |
|---|---|
| **Fund schemes analyzed** | 40 (across 10 fund houses) |
| **NAV history** | 46,000 daily records, Jan 2022 – May 2026 (4.4 years) |
| **Investor transactions** | 32,778 records (₹352 Cr total value) |
| **Live NAV feed** | 5 large-cap schemes via [mfapi.in](https://www.mfapi.in/) (AMFI mirror) |
| **Notebooks** | EDA, Performance Analytics, Advanced Risk Analytics |
| **Dashboard** | Power BI — investor transaction analytics by state / age group / type |

Key results: top-CAGR schemes reached **32.8%** (ICICI Pru Midcap), Historical
**VaR (5%) = -1.63%**, **CVaR = -2.98%**, and all 34 analyzed portfolios came
back with **HHI < 0.25** ("Diversified"). See `reports/` and
`Bluestock_MF_Final_Report_balugurisruthi61.pdf` for the full write-up.

---

## 2. Repository Structure

```
data-project/
├── data/
│   └── raw/
│       ├── 01_fund_master.csv          # 40 schemes: AMFI code, AMC, category, risk grade
│       ├── 02_nav_history.csv          # Daily NAV per scheme, Jan 2022 – May 2026
│       ├── 03_aum_by_fund_house.csv    # Quarterly AUM by AMC
│       ├── 04_monthly_sip_inflows.csv  # Monthly SIP inflows / active accounts
│       ├── 05_category_inflows.csv     # Monthly net inflows by fund category
│       ├── 06_industry_folio_count.csv # Total / equity folio growth
│       ├── 07_scheme_performance.csv   # Returns, Sharpe, AUM, rating, risk grade
│       ├── 08_investor_transactions.csv# 32,778 transaction-level records
│       ├── 09_portfolio_holdings.csv   # Stock-level holdings, 34 funds
│       ├── 10_benchmark_indices.csv    # NIFTY50/100/Midcap150/Smallcap, CRISIL indices
│       └── *_nav.csv                   # Live NAV files written by live_nav_fetch.py
├── notebooks/
│   ├── EDA_Analysis.ipynb              # AUM, SIP, folios, category inflows, sectors
│   ├── Performance_Analytics.ipynb     # CAGR, Sharpe, Sortino, Alpha/Beta, Max Drawdown
│   └── Advanced_Analytics.ipynb        # VaR, CVaR, rolling Sharpe, recommendations, HHI
├── reports/
│   ├── Bluestock_MF_Final_Report_balugurisruthi61.pdf
│   └── Bluestock_MF_Presentation_balugurisruthi61.pptx
├── fund_scorecard.csv                  # Output: CAGR, Sharpe, Sortino, Max Drawdown per scheme
├── alpha_beta.csv                      # Output: Alpha, Beta vs NIFTY50 per scheme
├── rolling_sharpe.csv                  # Output: 90-day rolling Sharpe series
├── live_nav_fetch.py                   # Stage 1 — fetch live NAV data
├── data_ingestion.py                   # Stage 2 — AMFI code validation
├── run_pipeline.py                     # Master script — runs the full pipeline
├── requirements.txt
└── README.md
```

---

## 3. Setup

```bash
# 1. Clone the repository
git clone https://github.com/balugurisruthi61-bot/data-project.git
cd data-project

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install scipy                # required by run_pipeline.py for Alpha/Beta regression
```

---

## 4. How to Run the Pipeline

The full pipeline can be run end-to-end with a single command:

```bash
python run_pipeline.py
```

This runs, in order:

1. **`fetch_live_nav()`** — downloads live NAV history for 5 large-cap
   schemes from `api.mfapi.in` and saves them to `data/raw/`.
2. **`validate_fund_data()`** — cross-checks AMFI codes between
   `01_fund_master.csv` and `02_nav_history.csv`. Expected result: **0
   mismatches** (40/40 schemes match).
3. **`compute_performance()`** — computes CAGR, Sharpe, Sortino, Alpha/Beta
   (vs NIFTY50) and Max Drawdown for all 40 schemes, writing
   `fund_scorecard.csv` and `alpha_beta.csv`.
4. **`compute_advanced_risk()`** — computes Historical VaR / CVaR, the
   90-day rolling Sharpe ratio (`rolling_sharpe.csv`), the top 3 low-risk
   fund recommendations, and portfolio concentration (HHI) for 34 funds.
5. **`print_summary()`** — prints a console summary of all the above.

### Useful flags

```bash
# Skip the live API calls and reuse existing files in data/raw/
python run_pipeline.py --skip-fetch

# Point at a different data folder
python run_pipeline.py --data-dir path/to/data/raw
```

### Running individual stages

The two original scripts can still be run on their own:

```bash
python live_nav_fetch.py     # Stage 1 only — refresh live NAV CSVs
python data_ingestion.py      # Stage 2 only — print the AMFI validation report
```

### Running the notebooks

Open the notebooks in Jupyter Lab/Notebook from the `notebooks/` folder
(paths inside the notebooks are relative to `notebooks/`, i.e.
`../data/raw/...`):

```bash
jupyter lab notebooks/
```

Run in order: `EDA_Analysis.ipynb` → `Performance_Analytics.ipynb` →
`Advanced_Analytics.ipynb`.

---

## 5. Dataset Descriptions

| File | Rows | Description |
|---|---|---|
| `01_fund_master.csv` | 40 | Scheme master — AMFI code, fund house, category, sub-category, expense ratio, fund manager, risk category |
| `02_nav_history.csv` | 46,000 | Daily NAV per AMFI code, Jan 2022 – May 2026 |
| `03_aum_by_fund_house.csv` | 91 | Quarterly AUM (₹ lakh crore) and scheme count per fund house, 2022–2025 |
| `04_monthly_sip_inflows.csv` | 48 | Monthly SIP inflow, active SIP accounts, SIP AUM |
| `05_category_inflows.csv` | 145 | Monthly net inflow by fund category |
| `06_industry_folio_count.csv` | 21 | Total / equity / debt / hybrid folio counts over time |
| `07_scheme_performance.csv` | 40 | 1Y/3Y/5Y returns, Sharpe, AUM, Morningstar rating, risk grade |
| `08_investor_transactions.csv` | 32,778 | Transaction-level: investor ID, date, AMFI code, type, amount, state, city tier, age group |
| `09_portfolio_holdings.csv` | 323 | Stock-level holdings — sector, weight %, market value, across 34 funds |
| `10_benchmark_indices.csv` | 8,051 | Daily values for NIFTY50 / NIFTY100 / NIFTY500 / Midcap150 / Smallcap, CRISIL Liquid / Gilt |

---

## 6. Power BI Dashboard

The dashboard visualizes `08_investor_transactions.csv` with the following pages/visuals:

- **Count of state by amount_inr** — transaction value by state
- **Sum of amount_inr by transaction_type** — Lumpsum / Redemption / SIP split
- **Count of age_group by amount_inr** — transaction value by investor age group
- **Sum of amount_inr by Year** — 2024 vs 2025 trend
- **Slicers**: `state`, `city_tier` (B30/T30), `age_group`

### To open the dashboard

1. Open Power BI Desktop (free).
2. **Get Data → Text/CSV** → select `data/raw/08_investor_transactions.csv`.
3. Recreate the visuals above, or open the included `.pbix` file (if
   provided in `reports/`) directly.
4. Use the **State**, **City Tier**, and **Age Group** slicers to drill
   down — e.g. filtering to *State = Tamil Nadu* reproduces the figures in
   Section 9 of the final report (₹315.18M total, 56.39% Lumpsum / 37.77%
   Redemption / 5.84% SIP).

---

## 7. Key Findings (Summary)

- **Data quality**: 0 AMFI code mismatches between fund master and NAV
  history — 40/40 schemes fully validated.
- **Top performer**: ICICI Pru Midcap Fund — 32.80% CAGR, Sharpe 1.18.
- **Best risk-adjusted**: Mirae Asset Large Cap Fund — 30.95% CAGR with the
  highest Sharpe (1.45) among the top-5 CAGR schemes.
- **Industry growth**: SIP inflows +169% and investor folios +97% from 2022
  to 2025.
- **Risk**: Historical VaR (5%) = -1.63%, CVaR = -2.98%.
- **Low-risk picks**: ICICI Pru Liquid, Kotak Liquid, and ABSL Liquid funds
  (Sharpe 7.68 / 6.18 / 5.14).
- **Diversification**: all 34 analyzed portfolios have HHI < 0.25
  ("Diversified"), despite some single-stock weights up to 38%.

Full details, charts, and methodology are in
`Bluestock_MF_Final_Report_balugurisruthi61.pdf`.

---

## 8. Limitations & Future Work

See Section 10 of the final report for the full discussion. In short:

- VaR/CVaR and the rolling Sharpe ratio are computed on the pooled NAV
  return series (industry-wide indicator) rather than per scheme.
- A flat 6.5% annual risk-free rate is used for Sharpe/Sortino across the
  full 4.4-year period.
- 2025 transaction data only covers January–May (partial year).
- The underlying datasets are illustrative/synthetic, generated for this
  capstone exercise (apart from the 5 live-fetched NAV series).

Planned improvements: extend live NAV fetching to all 40 schemes, use a
time-varying risk-free rate, and publish the dashboard to Power BI Service.

---

## 9. Tech Stack

- **Python**: pandas, numpy, scipy, requests, matplotlib
- **Notebooks**: Jupyter Lab
- **Dashboard**: Power BI Desktop
- **Data source**: [AMFI](https://www.amfiindia.com/) via [mfapi.in](https://www.mfapi.in/)

---

## 10. Disclaimer

This project was built for educational purposes as part of the Bluestock
Fintech internship capstone. The datasets are illustrative/synthetic and
the findings do not constitute investment advice.
