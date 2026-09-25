"""
laptop_3_retail_and_consumer.py
--------------------------------
Run this script on LAPTOP 3 (or alongside the GUI on Laptop 3).
Hosts both Retail (vendor.db) and Consumer Affairs (consumer_affairs.db)
on Port 5000 over Wi-Fi / Local Network.

Usage:
  python laptop_3_retail_and_consumer.py
"""

import os
import sys
import socket
from db_node import start_node

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    vendor_db = os.path.join(base_dir, "data", "vendor.db")
    ca_db = os.path.join(base_dir, "data", "consumer_affairs.db")

    if not os.path.exists(vendor_db) or not os.path.exists(ca_db):
        print("Databases not found. Running setup_sources.py...")
        from setup_sources import build_vendor_db, build_consumer_affairs_db
        build_vendor_db()
        build_consumer_affairs_db()

    local_ip = get_local_ip()
    port = 5000

    print("=" * 64)
    print("  [LAPTOP 3] RETAIL & CONSUMER AFFAIRS DATABASE NODE")
    print(f"  Local Wi-Fi IP : {local_ip}")
    print(f"  Port           : {port}")
    print(f"  Databases      : vendor.db (sales) & consumer_affairs.db (complaints)")
    print("=" * 64)

    start_node(
        port=port,
        node_name="LAPTOP 3: Retail & Consumer Node",
        db_mapping={
            "sales": vendor_db,
            "vendor": vendor_db,
            "complaints": ca_db,
            "consumer_affairs": ca_db
        }
    )

if __name__ == "__main__":
    main()
