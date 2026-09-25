"""
run_terminal_3_retail.py
-------------------------
Runs Instance 3 & 4: Retail & Consumer Node.
Hosts:
  - vendor.db (Point-of-Sale purchase scans) on Port 5003
  - consumer_affairs.db (Official fraud reports) on Port 5004

This runs both consumer-facing databases concurrently inside this terminal!

Usage:
  python run_terminal_3_retail.py
"""

import os
import sys
import time
from db_node import start_node

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_db = os.path.join(base_dir, "data", "vendor.db")
    ca_db = os.path.join(base_dir, "data", "consumer_affairs.db")

    if not os.path.exists(vendor_db) or not os.path.exists(ca_db):
        print("Databases not found. Running setup_sources.py...")
        from setup_sources import build_vendor_db, build_consumer_affairs_db
        build_vendor_db()
        build_consumer_affairs_db()

    print("================================================================")
    print("[*] TERMINAL 3: Retail & Consumer Node Starting...")
    print("================================================================")

    # Start vendor node in background thread within this terminal
    server_v, thread_v = start_node(
        db_path=vendor_db,
        port=5003,
        node_name="Retail Vendor Node",
        threaded=True
    )

    # Start consumer affairs node on main thread
    try:
        start_node(
            db_path=ca_db,
            port=5004,
            node_name="Consumer Affairs Node",
            threaded=False
        )
    except KeyboardInterrupt:
        print("\n[!] Stopping Terminal 3 database services...")
        server_v.server_close()
        print("Terminal 3 stopped.")

if __name__ == "__main__":
    main()
