"""
data_ingestion.py
==================

Loads the fund master and NAV history datasets and validates that every
AMFI scheme code is present in both files. This is the data-quality gate
that must pass before any downstream EDA or analytics is run.

Run directly to print a validation report:

    python data_ingestion.py

Exit status is 0 whether or not mismatches are found — mismatches are
reported but do not stop the script, so it can be used for monitoring as
well as one-off checks.
"""

import pandas as pd

FUND_MASTER_PATH = "data/raw/01_fund_master.csv"
NAV_HISTORY_PATH = "data/raw/02_nav_history.csv"


def load_datasets(fund_master_path=FUND_MASTER_PATH, nav_history_path=NAV_HISTORY_PATH):
    """Load the fund master and NAV history CSVs.

    Parameters
    ----------
    fund_master_path : str
        Path to ``01_fund_master.csv``.
    nav_history_path : str
        Path to ``02_nav_history.csv``.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame]
        ``(fund_master, nav_history)``.
    """
    fund_master = pd.read_csv(fund_master_path)
    nav_history = pd.read_csv(nav_history_path)
    return fund_master, nav_history


def validate_amfi_codes(fund_master, nav_history):
    """Cross-validate AMFI codes between fund master and NAV history.

    Parameters
    ----------
    fund_master : pandas.DataFrame
        Must contain an ``amfi_code`` column.
    nav_history : pandas.DataFrame
        Must contain an ``amfi_code`` column.

    Returns
    -------
    tuple[set, set]
        ``(missing_in_nav_history, missing_in_fund_master)`` — AMFI codes
        present in one file but not the other.
    """
    fund_codes = set(fund_master["amfi_code"])
    nav_codes = set(nav_history["amfi_code"])

    missing_in_nav_history = fund_codes - nav_codes
    missing_in_fund_master = nav_codes - fund_codes

    return missing_in_nav_history, missing_in_fund_master


def main():
    """Load datasets, run the AMFI code validation, and print a report."""
    fund_master, nav_history = load_datasets()
    missing_in_nav, missing_in_master = validate_amfi_codes(fund_master, nav_history)

    print(f"Fund master schemes : {fund_master['amfi_code'].nunique()}")
    print(f"NAV history schemes : {nav_history['amfi_code'].nunique()}")
    print(f"Missing AMFI Codes Count (in NAV history): {len(missing_in_nav)}")
    print(f"Missing Codes (in NAV history): {missing_in_nav}")
    print(f"Missing AMFI Codes Count (in fund master): {len(missing_in_master)}")
    print(f"Missing Codes (in fund master): {missing_in_master}")

    if not missing_in_nav and not missing_in_master:
        print("\nValidation PASSED: all AMFI codes match between "
              "fund master and NAV history.")
    else:
        print("\nValidation WARNING: AMFI code mismatch detected (see above).")


if __name__ == "__main__":
    main()
