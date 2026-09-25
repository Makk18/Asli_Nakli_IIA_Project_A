"""
run_terminal_2_distributor.py
------------------------------
Runs Instance 2: Distributor Database on Port 5002.
Records authorized logistics and wholesale supply-chain dispatches.

Usage:
  python run_terminal_2_distributor.py
"""

import os
import sys
from db_node import start_node

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "data", "distributor.db")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Running setup_sources.py...")
        from setup_sources import build_distributor_db
        build_distributor_db()

    start_node(
        db_path=db_path,
        port=5002,
        node_name="TERMINAL 2: Distributor Node"
    )

if __name__ == "__main__":
    main()
