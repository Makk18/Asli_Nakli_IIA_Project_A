"""
logger.py
---------
Centralized Process and Activity Logger with Timestamps for Asli ya Nakli.
Records all operations:
  - Federated Queries (Wi-Fi network fetches from Laptop 1, 2, 3)
  - Decision Engine evaluations (rule checks & verdicts)
  - Live SQL Console executions
  - Manual Database insertions / updates / deletions
  - Warehouse Materialization & Maintenance events
"""

import os
import json
import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity_logs.json")

def log_event(category: str, action: str, details: str, status: str = "SUCCESS", node: str = "Mediator"):
    """
    Logs an event with a high-precision timestamp.
    Categories: FEDERATION, DECISION_ENGINE, SQL_QUERY, DATA_ENTRY, WAREHOUSE, SYSTEM
    Status: SUCCESS, WARNING, ERROR, INFO
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    entry = {
        "timestamp": timestamp,
        "category": category.upper(),
        "action": action,
        "details": details,
        "status": status.upper(),
        "node": node
    }

    logs = get_logs()
    logs.insert(0, entry)  # Prepend newest first
    # Keep last 500 logs
    logs = logs[:500]

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except Exception:
        pass
    return entry

def get_logs(limit: int = 200, category_filter: str = None):
    """Retrieves logs, optionally filtered by category."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
            if category_filter and category_filter != "ALL":
                logs = [l for l in logs if l.get("category") == category_filter]
            return logs[:limit]
    except Exception:
        return []

def clear_logs():
    """Clears the log history."""
    try:
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except Exception:
        pass
