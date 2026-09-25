"""
laptop_1_manufacturer.py
-------------------------
Run this script on LAPTOP 1.
Hosts the Manufacturer Database on Port 5000 over Wi-Fi / Local Network.

Usage:
  python laptop_1_manufacturer.py
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
    db_path = os.path.join(base_dir, "data", "manufacturer.db")

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Running setup_sources.py...")
        from setup_sources import build_manufacturer_db
        build_manufacturer_db()

    local_ip = get_local_ip()
    port = 5000

    print("=" * 64)
    print("  [LAPTOP 1] MANUFACTURER DATABASE NODE")
    print(f"  Local Wi-Fi IP : {local_ip}")
    print(f"  Port           : {port}")
    print(f"  Enter on Laptop 3 GUI: http://{local_ip}:{port}")
    print("=" * 64)

    start_node(
        db_path=db_path,
        port=port,
        node_name="LAPTOP 1: Manufacturer Node"
    )

if __name__ == "__main__":
    main()
