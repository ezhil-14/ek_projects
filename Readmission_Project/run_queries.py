"""
Phase 3: Run every query in queries.sql, print the results,
and save each one to outputs/<query name>.csv for the dashboard.

Run:  python run_queries.py              (all queries)
      python run_queries.py q04          (only queries whose name starts with q04)
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/hospital.db")
SQL_FILE = Path("queries.sql")
OUT_DIR = Path("outputs")


def load_queries(path: Path) -> dict:
    """Split queries.sql into {name: sql} using the '-- name:' markers."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"^--\s*name:\s*(\S+)\s*$", text, flags=re.MULTILINE)
    # parts = [header, name1, sql1, name2, sql2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main():
    OUT_DIR.mkdir(exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    queries = load_queries(SQL_FILE)

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)

    with sqlite3.connect(DB_PATH) as conn:
        for name, sql in queries.items():
            if not name.startswith(only):
                continue
            df = pd.read_sql_query(sql, conn)
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)

            print("=" * 80)
            print(f"{name}   ({len(df):,} rows -> outputs/{name}.csv)")
            print("=" * 80)
            print(df.head(15).to_string(index=False))
            if len(df) > 15:
                print(f"... {len(df) - 15:,} more rows in the CSV")
            print()


if __name__ == "__main__":
    main()
