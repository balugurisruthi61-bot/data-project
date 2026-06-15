"""
live_nav_fetch.py
==================

Fetches live NAV (Net Asset Value) history for a set of large-cap mutual
fund schemes from the AMFI mfapi.in API and saves each scheme's history as
a CSV file under ``data/raw/``.

This is the standalone version of Stage 1 of ``run_pipeline.py``. Run it
directly to (re)download the latest NAV history for the 5 tracked schemes:

    python live_nav_fetch.py

Output
------
For each scheme, a file ``data/raw/{scheme_name}_nav.csv`` is created with
columns ``date`` and ``nav`` (as returned by the mfapi.in API).
"""

import os

import pandas as pd
import requests

# AMFI scheme codes for the 5 large-cap funds tracked with live NAV data.
SCHEMES = {
    "SBI_Bluechip": 119551,
    "ICICI_Bluechip": 120503,
    "Nippon_Large_Cap": 118632,
    "Axis_Bluechip": 119092,
    "Kotak_Bluechip": 120841,
}

DATA_DIR = "data/raw"


def fetch_nav_history(scheme_name, amfi_code, data_dir=DATA_DIR):
    """Fetch and save NAV history for a single scheme.

    Parameters
    ----------
    scheme_name : str
        Friendly name used for the output file, e.g. ``"SBI_Bluechip"``.
    amfi_code : int
        The scheme's AMFI code, e.g. ``119551``.
    data_dir : str
        Folder where ``{scheme_name}_nav.csv`` will be written.

    Returns
    -------
    bool
        ``True`` if the data was fetched and saved successfully,
        ``False`` if the request failed.
    """
    url = f"https://api.mfapi.in/mf/{amfi_code}"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"[ERROR] {scheme_name} (AMFI {amfi_code}): {exc}")
        return False

    os.makedirs(data_dir, exist_ok=True)
    out_path = os.path.join(data_dir, f"{scheme_name}_nav.csv")
    pd.DataFrame(data["data"]).to_csv(out_path, index=False)

    print(f"{scheme_name} saved -> {out_path}")
    return True


def main():
    """Fetch NAV history for every scheme in ``SCHEMES``."""
    for name, code in SCHEMES.items():
        fetch_nav_history(name, code)


if __name__ == "__main__":
    main()
