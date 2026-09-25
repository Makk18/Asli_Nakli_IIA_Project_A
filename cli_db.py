"""
cli_db.py
---------
Interactive SQL Shell for Individual Laptops.
Allows running direct INSERT, UPDATE, DELETE, and SELECT statements on the local database.

Usage on any laptop:
  python cli_db.py
"""

import sqlite3
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

def list_databases():
    if not os.path.exists(DATA_DIR):
        return []
    return [f for f in os.listdir(DATA_DIR) if f.endswith(".db")]

def main():
    dbs = list_databases()
    if not dbs:
        print("[!] No database files found in ./data/. Run setup_sources.py first.")
        return

    # print("=" * 60)
    # print("  💻 Asli ya Nakli — Local Database SQL Terminal")
    # print("=" * 60)
    # print("Available local databases on this laptop:")
    # for idx, db in enumerate(dbs, 1):
    #     print(f"  [{idx}] {db}")
    # print("=" * 60)

    choice = input(f"Select database [1-{len(dbs)}] (or press Enter for [1]): ").strip()
    idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(dbs) else 0
    selected_db = dbs[idx]
    db_path = os.path.join(DATA_DIR, selected_db)

    print(f"\nConnected to: {selected_db}")
    print("Type your SQL commands (INSERT, UPDATE, DELETE, SELECT).")
    print("Type 'exit' or 'quit' to close.\n")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Show existing tables and columns
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    print("Tables in this database:")
    for t in tables:
        cols = cur.execute(f"PRAGMA table_info({t[0]})").fetchall()
        col_names = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
        print(f"  - {t[0]}: ({col_names})")
    print("-" * 60)

    while True:
        try:
            sql = input(f"{selected_db}> ").strip()
            if not sql:
                continue
            if sql.lower() in ["exit", "quit", "q"]:
                break

            cur.execute(sql)
            if sql.upper().startswith("SELECT") or sql.upper().startswith("PRAGMA"):
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
                if cols:
                    print(" | ".join(cols))
                    print("-" * (len(" | ".join(cols)) + 10))
                for r in rows:
                    print(" | ".join(str(val) for val in r))
                print(f"({len(rows)} row(s) returned)\n")
            else:
                conn.commit()
                print(f"Query executed successfully. Rows affected: {cur.rowcount}\n")
        except Exception as e:
            print(f"Error: {e}\n")

    conn.close()
    print("Connection closed.")

if __name__ == "__main__":
    main()
