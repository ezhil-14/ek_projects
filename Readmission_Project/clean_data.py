"""
Phase 2: Clean the two CMS files, join them, and save an analysis-ready table.

Folder layout:
    hospital-readmissions-analysis/
        data/raw/          <- original CMS CSVs (never edited)
        data/processed/    <- created by this script
        data/hospital.db   <- SQLite database (from Phase 1, updated here)
        clean_data.py      <- this script

Run:  python clean_data.py
"""
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
DB_PATH = Path("data/hospital.db")

HRRP_FILE = RAW_DIR / "FY_2026_Hospital_Readmissions_Reduction_Program_Hospital.csv"
INFO_FILE = RAW_DIR / "Hospital_General_Information.csv"

# Every placeholder CMS uses instead of a real value.
# pandas already treats "N/A" and blanks as missing by default.
MISSING = ["N/A", "Not Available", "Too Few to Report", "Too Few to Measure", "Not Applicable"]

# Readable names for the six HRRP conditions
CONDITIONS = {
    "READM-30-AMI-HRRP": "Heart Attack (AMI)",
    "READM-30-HF-HRRP": "Heart Failure",
    "READM-30-PN-HRRP": "Pneumonia",
    "READM-30-COPD-HRRP": "COPD",
    "READM-30-HIP-KNEE-HRRP": "Hip/Knee Replacement",
    "READM-30-CABG-HRRP": "Heart Bypass (CABG)",
}


def snake(col: str) -> str:
    """'Excess Readmission Ratio' -> 'excess_readmission_ratio'"""
    return (
        col.strip().lower()
        .replace("/", "_").replace("-", "_").replace(" ", "_")
    )


def clean_hrrp() -> pd.DataFrame:
    df = pd.read_csv(HRRP_FILE, dtype=str, na_values=MISSING)
    df.columns = [snake(c) for c in df.columns]

    # Numbers were read as text; convert them
    numeric_cols = [
        "number_of_discharges", "excess_readmission_ratio",
        "predicted_readmission_rate", "expected_readmission_rate",
        "number_of_readmissions",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["start_date"] = pd.to_datetime(df["start_date"], format="%m/%d/%Y")
    df["end_date"] = pd.to_datetime(df["end_date"], format="%m/%d/%Y")

    # Readable condition name
    df["condition"] = df["measure_name"].map(CONDITIONS)
    unmapped = df.loc[df["condition"].isna(), "measure_name"].unique()
    if len(unmapped):
        print(f"WARNING: unknown measure names: {unmapped}")

    # Flags used throughout the analysis
    df["has_ratio"] = df["excess_readmission_ratio"].notna()
    df["above_expected"] = np.where(
        df["has_ratio"], df["excess_readmission_ratio"] > 1, np.nan
    )
    # Percentage-point gap between this hospital and an average hospital
    # with the same patient mix
    df["excess_rate_points"] = (
        df["predicted_readmission_rate"] - df["expected_readmission_rate"]
    )
    return df


def clean_info() -> pd.DataFrame:
    df = pd.read_csv(INFO_FILE, dtype=str, na_values=MISSING)

    keep = {
        "Facility ID": "facility_id",
        "City/Town": "city",
        "County/Parish": "county",
        "ZIP Code": "zip_code",
        "Hospital Type": "hospital_type",
        "Hospital Ownership": "hospital_ownership",
        "Emergency Services": "emergency_services",
        "Hospital overall rating": "star_rating",
        "Count of Facility READM Measures": "readm_measures_reported",
        "Count of READM Measures Better": "readm_measures_better",
        "Count of READM Measures No Different": "readm_measures_no_different",
        "Count of READM Measures Worse": "readm_measures_worse",
    }
    df = df[list(keep)].rename(columns=keep)

    for col in ["star_rating", "readm_measures_reported", "readm_measures_better",
                "readm_measures_no_different", "readm_measures_worse"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Group the many ownership labels into four groups for the dashboard
    def ownership_group(x):
        if pd.isna(x):
            return np.nan
        x = x.lower()
        if "proprietary" in x:
            return "For-profit"
        if "voluntary non-profit" in x:
            return "Non-profit"
        if "government" in x:
            return "Government"
        return "Other"

    df["ownership_group"] = df["hospital_ownership"].map(ownership_group)
    return df


def check(df: pd.DataFrame, hrrp: pd.DataFrame, info: pd.DataFrame):
    """Print a short validation report. Read it before moving on."""
    print("=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)

    print(f"\nHRRP rows: {len(hrrp):,}   unique hospitals: {hrrp['facility_id'].nunique():,}")
    print(f"General info hospitals: {len(info):,}")
    print(f"Duplicate IDs in general info: {info['facility_id'].duplicated().sum()}")

    unmatched = set(hrrp["facility_id"]) - set(info["facility_id"])
    print(f"HRRP hospitals with no match in general info: {len(unmatched)}")

    print("\nRows with a usable ratio, by condition:")
    cov = df.groupby("condition")["has_ratio"].agg(["sum", "count"])
    cov["pct"] = (cov["sum"] / cov["count"] * 100).round(1)
    print(cov.rename(columns={"sum": "with_ratio", "count": "total"}).to_string())

    # Sanity check: the ratio should equal predicted / expected
    r = df.dropna(subset=["excess_readmission_ratio", "predicted_readmission_rate",
                          "expected_readmission_rate"])
    diff = (r["predicted_readmission_rate"] / r["expected_readmission_rate"]
            - r["excess_readmission_ratio"]).abs()
    print(f"\nRatio = predicted / expected check: max difference {diff.max():.4f} "
          f"(should be close to 0)")

    print("\nExcess readmission ratio summary:")
    print(df["excess_readmission_ratio"].describe().round(3).to_string())

    pct_above = df.loc[df["has_ratio"], "above_expected"].mean() * 100
    print(f"\nShare of condition rows above expected (ratio > 1): {pct_above:.1f}%")

    print(f"\nPerformance period: {df['start_date'].min():%b %d, %Y} "
          f"to {df['end_date'].max():%b %d, %Y}")

    al = df[df["state"] == "AL"]
    print(f"\nAlabama: {al['facility_id'].nunique()} hospitals, {len(al)} rows")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    hrrp = clean_hrrp()
    info = clean_info()

    # Left join: keep every HRRP row, add hospital details where available
    df = hrrp.merge(info, on="facility_id", how="left", validate="many_to_one")

    check(df, hrrp, info)

    # Save
    df.to_csv(OUT_DIR / "readmissions_clean.csv", index=False)
    info.to_csv(OUT_DIR / "hospital_info_clean.csv", index=False)

    with sqlite3.connect(DB_PATH) as conn:
        out = df.copy()
        out["start_date"] = out["start_date"].dt.strftime("%Y-%m-%d")
        out["end_date"] = out["end_date"].dt.strftime("%Y-%m-%d")
        out.to_sql("readmissions", conn, if_exists="replace", index=False)
        info.to_sql("hospitals", conn, if_exists="replace", index=False)

    print("\nSaved:")
    print(f"  {OUT_DIR / 'readmissions_clean.csv'}  ({len(df):,} rows)")
    print(f"  {OUT_DIR / 'hospital_info_clean.csv'}  ({len(info):,} rows)")
    print(f"  SQLite tables 'readmissions' and 'hospitals' in {DB_PATH}")


if __name__ == "__main__":
    main()
