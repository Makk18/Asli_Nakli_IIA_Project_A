"""
db_node.py
----------
Lightweight HTTP Database Server Instance for Asli ya Nakli Distributed Architecture.
Each instance serves one SQLite database over a dedicated TCP/HTTP port.

Endpoints:
  - GET  /health   -> { "status": "ok", "db": db_name, "node": node_name, "port": port }
  - GET  /schema   -> { "tables": [ { "name": ..., "columns": [...] } ] }
  - POST /query    -> payload: { "sql": "...", "params": [...] } -> { "columns": [...], "rows": [...] }
  - POST /execute  -> payload: { "sql": "...", "params": [...] } -> { "rows_affected": ..., "last_insert_rowid": ... }
  - POST /insert   -> payload: { "table": "...", "data": { "col": val, ... } }
"""

import sqlite3
import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

class DBNodeHandler(BaseHTTPRequestHandler):
    db_path = None
    db_mapping = None  # Optional dict: { "table_name": db_path } or { "db_name": db_path }
    node_name = None
    port = None

    def log_message(self, format, *args):
        # Custom logging with terminal-friendly timestamp and node name
        sys.stdout.write(f"[{self.node_name}:{self.port}] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

    def _get_target_db(self, query_sql="", requested_db=""):
        """Resolves target db path when multiple databases are hosted on this laptop."""
        if self.db_mapping:
            if requested_db and requested_db in self.db_mapping:
                return self.db_mapping[requested_db]
            # Infer from SQL query text if table name appears
            q_upper = query_sql.upper()
            for key, path in self.db_mapping.items():
                if key.upper() in q_upper:
                    return path
            # Default to first mapped database
            return list(self.db_mapping.values())[0]
        return self.db_path

    def _send_json(self, status_code, data):
        response = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(response)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health" or path == "/":
            db_label = list(self.db_mapping.keys()) if self.db_mapping else os.path.basename(self.db_path)
            self._send_json(200, {
                "status": "online",
                "node": self.node_name,
                "port": self.port,
                "databases": db_label
            })
            return

        if path == "/schema":
            try:
                all_schema = []
                targets = list(self.db_mapping.values()) if self.db_mapping else [self.db_path]
                for target_db in set(targets):
                    conn = sqlite3.connect(target_db)
                    cur = conn.cursor()
                    tables_raw = cur.execute(
                        "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                    for name, t_type in tables_raw:
                        cols_info = cur.execute(f"PRAGMA table_info('{name}')").fetchall()
                        cols = [{"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "pk": c[5]} for c in cols_info]
                        all_schema.append({"name": name, "type": t_type, "columns": cols, "db": os.path.basename(target_db)})
                    conn.close()
                self._send_json(200, {"status": "ok", "schema": all_schema})
            except Exception as e:
                self._send_json(500, {"status": "error", "error": str(e)})
            return

        self._send_json(404, {"status": "error", "error": f"Unknown endpoint: {path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError as e:
            self._send_json(400, {"status": "error", "error": f"Invalid JSON body: {str(e)}"})
            return

        conn = None
        try:
            sql = payload.get("sql", "")
            target_db_name = payload.get("db", "")
            target_db_path = self._get_target_db(sql, target_db_name)

            conn = sqlite3.connect(target_db_path)
            cur = conn.cursor()

            if path == "/query":
                params = payload.get("params", [])
                if not sql.strip():
                    self._send_json(400, {"status": "error", "error": "Empty SQL query provided"})
                    return

                cur.execute(sql, params)
                cols = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall()
                self._send_json(200, {
                    "status": "ok",
                    "columns": cols,
                    "rows": rows,
                    "rowcount": len(rows),
                    "db_served": os.path.basename(target_db_path)
                })

            elif path == "/execute":
                params = payload.get("params", [])
                if not sql.strip():
                    self._send_json(400, {"status": "error", "error": "Empty SQL command provided"})
                    return

                if ";" in sql.strip() and not params:
                    cur.executescript(sql)
                    affected = cur.rowcount
                    last_id = cur.lastrowid
                else:
                    cur.execute(sql, params)
                    affected = cur.rowcount
                    last_id = cur.lastrowid

                conn.commit()
                self._send_json(200, {
                    "status": "ok",
                    "rows_affected": affected,
                    "last_insert_rowid": last_id,
                    "db_served": os.path.basename(target_db_path)
                })

            elif path == "/insert":
                table = payload.get("table", "")
                data = payload.get("data", {})
                if not table or not data:
                    self._send_json(400, {"status": "error", "error": "Both 'table' and 'data' dict are required."})
                    return

                keys = list(data.keys())
                values = [data[k] for k in keys]
                placeholders = ", ".join(["?"] * len(keys))
                col_names = ", ".join(keys)
                query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

                cur.execute(query, values)
                conn.commit()
                self._send_json(200, {
                    "status": "ok",
                    "rows_affected": cur.rowcount,
                    "last_insert_rowid": cur.lastrowid,
                    "db_served": os.path.basename(target_db_path)
                })

            else:
                self._send_json(404, {"status": "error", "error": f"Unknown endpoint: {path}"})

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self._send_json(500, {"status": "error", "error": str(e)})
        finally:
            if conn:
                conn.close()


def start_node(db_path=None, port=5000, node_name="Database Node", db_mapping=None, threaded=False):
    class CustomHandler(DBNodeHandler):
        pass

    CustomHandler.db_path = os.path.abspath(db_path) if db_path else None
    CustomHandler.db_mapping = {k: os.path.abspath(v) for k, v in db_mapping.items()} if db_mapping else None
    CustomHandler.node_name = node_name
    CustomHandler.port = port

    server = HTTPServer(("0.0.0.0", port), CustomHandler)
    print("================================================================")
    print(f"[*] {node_name} running on port {port}")
    if db_mapping:
        for k, v in db_mapping.items():
            print(f"    - Database mapping: [{k}] -> {os.path.basename(v)}")
    elif db_path:
        print(f"    - Database: {os.path.basename(db_path)}")
    print(f"[*] Listening on all interfaces (0.0.0.0:{port}) for Wi-Fi communication...")
    print("================================================================")

    if threaded:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread
    else:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print(f"\n[!] Stopping {node_name}...")
            server.server_close()
            print("Server stopped.")
