"""
run_terminal_1_manufacturer.py
-------------------------------
Runs Instance 1: Manufacturer Database on Port 5001.
Source of truth for genuine registered pharmaceutical products.

Usage:
  python run_terminal_1_manufacturer.py
"""

import os
import sys
from db_node import start_node

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "data", "manufacturer.db")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Running setup_sources.py...")
        from setup_sources import build_manufacturer_db
        build_manufacturer_db()

    start_node(
        db_path=db_path,
        port=5001,
        node_name="TERMINAL 1: Manufacturer Node"
    )

if __name__ == "__main__":
    main()
