"""
config.py
---------
Central Configuration for 3-Laptop Distributed Federation.
Eliminates 4 local port confusion by using a single standard port (5000) per laptop.

Laptop 1: Manufacturer Node (Port 5000)
Laptop 2: Distributor Node  (Port 5000)
Laptop 3: Retail & Consumer Node (Port 5000) + Central Mediator GUI (Port 8501)
"""

import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cluster_config.json")

# Default configuration: if all running on 1 laptop for testing, uses 127.0.0.1
# When running across 3 laptops on Wi-Fi, replace with the respective laptop IPs!
DEFAULT_CONFIG = {
    "laptop_1_mfr": {
        "name": "Laptop 1 (Manufacturer)",
        "host": "127.0.0.1",
        "port": 5000,
        "db": "manufacturer.db"
    },
    "laptop_2_dist": {
        "name": "Laptop 2 (Distributor)",
        "host": "127.0.0.1",
        "port": 5000,
        "db": "distributor.db"
    },
    "laptop_3_retail": {
        "name": "Laptop 3 (Retail & Consumer)",
        "host": "127.0.0.1",
        "port": 5000,
        "db": "vendor.db & consumer_affairs.db"
    }
}

def load_config():
    """Loads configuration from cluster_config.json or returns defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                config = DEFAULT_CONFIG.copy()
                for k, v in saved.items():
                    if k in config:
                        config[k].update(v)
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config_data):
    """Saves updated laptop IP addresses to cluster_config.json."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f, indent=4)

def get_node_url(node_key):
    """Returns the full HTTP URL for a given laptop node."""
    cfg = load_config()
    node = cfg.get(node_key)
    if not node:
        return "http://127.0.0.1:5000"
    host = node.get("host", "127.0.0.1").strip()
    port = node.get("port", 5000)
    # If host already has protocol (http:// or https://)
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"http://{host}:{port}"
