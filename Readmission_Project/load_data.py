"""
Phase 1: Load the CMS CSV files into a SQLite database and profile them.

Folder layout expected:
    hospital-readmissions-analysis/
        data/raw/        <- put the downloaded CMS CSV files here
        load_data.py     <- this script

Run:  python load_data.py
"""
import re
import sqlite3
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
DB_PATH = Path("data/hospital.db")

# Placeholder text CMS uses instead of real values
MISSING_MARKERS = ["N/A", "Not Available", "Too Few to Measure", "Not Applicable"]


def table_name(path: Path) -> str:
    """Turn a file name into a clean SQL table name."""
    name = re.sub(r"[^0-9a-zA-Z]+", "_", path.stem).strip("_").lower()
    return name


def main():
    csv_files = sorted(RAW_DIR.glob("*.csv"))
    if not csv_files:
        print(f"No CSV files found in {RAW_DIR.resolve()}")
        return

    conn = sqlite3.connect(DB_PATH)

    for path in csv_files:
        # Read everything as text first: Facility IDs have leading zeros
        # (e.g. 010001 for Alabama) that would be lost if read as numbers.
        df = pd.read_csv(path, dtype=str)
        name = table_name(path)

        print("=" * 70)
        print(f"FILE:  {path.name}")
        print(f"TABLE: {name}")
        print(f"Rows: {len(df):,}   Columns: {df.shape[1]}")

        print("\nColumns:")
        for col in df.columns:
            n_blank = df[col].isna().sum()
            n_marker = df[col].isin(MISSING_MARKERS).sum()
            print(f"  - {col:<45} blank: {n_blank:>6,}   placeholder text: {n_marker:>6,}")

        print("\nFirst 3 rows:")
        print(df.head(3).to_string())

        # Show which placeholder values appear, so we can plan cleaning
        found = {m: int((df == m).sum().sum()) for m in MISSING_MARKERS}
        found = {k: v for k, v in found.items() if v}
        if found:
            print(f"\nPlaceholder values found: {found}")

        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"\nLoaded into SQLite table '{name}'.\n")

    conn.close()
    print(f"Done. Database saved at {DB_PATH.resolve()}")


if __name__ == "__main__":
    main()
