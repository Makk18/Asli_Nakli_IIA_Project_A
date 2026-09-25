"""
setup_sources.py
-----------------
Creates FOUR independent SQLite databases, each simulating a real-world
system that was designed in isolation (as the assignment requires):

  1. manufacturer.db   -> table: products      (source of truth for what's genuine)
  2. distributor.db    -> table: distribution   (supply chain records)
  3. vendor.db          -> table: sales          (point-of-sale scans)
  4. consumer_affairs.db -> table: complaints    (fraud reports)

IMPORTANT (this is the whole point of the assignment): all four tables
refer to the SAME real-world attribute -- the item's unique code -- but
each source calls it something different:

    products.mfr_item_code
    distribution.supplier_code
    sales.scanned_code
    complaints.flagged_code

That naming mismatch is exactly the "heterogeneous schema" problem the
brief asks you to create. We solve it later in federation.py with
canonical mapping views, NOT by renaming these columns here.
"""

import sqlite3
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def path(name):
    return os.path.join(DATA_DIR, name)


def fresh_db(name):
    """Delete any existing file so re-running this script is idempotent."""
    p = path(name)
    if os.path.exists(p):
        os.remove(p)
    return sqlite3.connect(p)


# ---------------------------------------------------------------------
# 1. MANUFACTURER DB  (ground truth: if a code isn't here, it was never
#    made by a real manufacturer -> that alone is fraud evidence)
# ---------------------------------------------------------------------
def build_manufacturer_db():
    conn = fresh_db("manufacturer.db")
    conn.execute("""
        CREATE TABLE products (
            mfr_item_code   TEXT PRIMARY KEY,
            item_name       TEXT NOT NULL,
            manufacturer_name TEXT NOT NULL,
            batch_no        TEXT,
            mfg_date        TEXT,
            expiry_date     TEXT,
            mrp             REAL
        )
    """)
    rows = [
        ("MED-1001", "Paracetamol 500mg",  "Cipla Ltd",      "B22A", "2025-01-10", "2027-01-10", 25.0),
        ("MED-1002", "Amoxicillin 250mg",  "Sun Pharma",     "B45C", "2025-03-05", "2027-03-05", 60.0),
        ("MED-1003", "Cetirizine 10mg",    "Dr. Reddy's",    "B77Z", "2025-02-20", "2027-02-20", 18.0),
        ("MED-1004", "Metformin 500mg",    "Cipla Ltd",      "B90X", "2025-04-15", "2027-04-15", 40.0),
        ("MED-1005", "Azithromycin 500mg", "Sun Pharma",     "B12Q", "2025-05-01", "2027-05-01", 90.0),
        # NOTE: "MED-9999" deliberately does NOT exist here -- it will
        # show up at a vendor's counter but with no manufacturer record
        # at all, which is the clearest possible fake-item signal.
    ]
    conn.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# 2. DISTRIBUTOR / SUPPLIER DB  (the legitimate supply chain)
# ---------------------------------------------------------------------
def build_distributor_db():
    conn = fresh_db("distributor.db")
    conn.execute("""
        CREATE TABLE distribution (
            dist_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_code   TEXT NOT NULL,
            distributor_name TEXT NOT NULL,
            vendor_name     TEXT NOT NULL,
            qty             INTEGER,
            dispatch_date   TEXT,
            region          TEXT
        )
    """)
    rows = [
        ("MED-1001", "MedLine Distributors", "Apollo Pharmacy",    500, "2025-06-01", "Delhi NCR"),
        ("MED-1002", "MedLine Distributors", "Apollo Pharmacy",    300, "2025-06-02", "Delhi NCR"),
        ("MED-1003", "HealthChain Supply",   "Wellness Forever",   400, "2025-06-03", "Mumbai"),
        # MED-1004 note: exists at the manufacturer but was NEVER
        # dispatched through any authorised distributor -> if it still
        # turns up at a vendor, that's suspicious (grey-market / diverted stock).
        ("MED-1005", "HealthChain Supply",   "MedPlus",            250, "2025-06-05", "Bengaluru"),
    ]
    conn.executemany(
        "INSERT INTO distribution (supplier_code, distributor_name, vendor_name, qty, dispatch_date, region) "
        "VALUES (?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# 3. VENDOR DB  (what actually gets scanned/sold at the counter --
#    this is the "item in your hand right now" the use-case talks about)
# ---------------------------------------------------------------------
def build_vendor_db():
    conn = fresh_db("vendor.db")
    conn.execute("""
        CREATE TABLE sales (
            sale_id         INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_code    TEXT NOT NULL,
            description     TEXT,
            vendor_id       TEXT,
            sale_price      REAL,
            sale_date       TEXT
        )
    """)
    rows = [
        ("MED-1001", "Paracetamol 500mg strip",  "Apollo Pharmacy",  28.0, "2026-09-10"),
        ("MED-1002", "Amoxicillin 250mg capsule", "Apollo Pharmacy",  65.0, "2026-09-11"),
        ("MED-1003", "Cetirizine 10mg tablet",    "Wellness Forever", 20.0, "2026-09-12"),
        ("MED-1004", "Metformin 500mg tablet",    "MedPlus",          42.0, "2026-09-12"),  # no distributor record!
        ("MED-1005", "Azithromycin 500mg",        "MedPlus",          95.0, "2026-09-13"),
        ("MED-9999", "Paracetamol 500mg (loose)", "Roadside Kiosk",   15.0, "2026-09-14"),  # not a real code at all
    ]
    conn.executemany(
        "INSERT INTO sales (scanned_code, description, vendor_id, sale_price, sale_date) "
        "VALUES (?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# 4. CONSUMER AFFAIRS DB  (fraud reports filed against specific codes)
# ---------------------------------------------------------------------
def build_consumer_affairs_db():
    conn = fresh_db("consumer_affairs.db")
    conn.execute("""
        CREATE TABLE complaints (
            complaint_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            flagged_code    TEXT NOT NULL,
            reason          TEXT,
            reported_on     TEXT,
            status          TEXT
        )
    """)
    rows = [
        ("MED-1004", "Packaging looked tampered, no distributor seal", "2026-09-13", "Under Investigation"),
        ("MED-9999", "Code does not exist in any manufacturer database", "2026-09-14", "Verified Nakli"),
    ]
    conn.executemany(
        "INSERT INTO complaints (flagged_code, reason, reported_on, status) VALUES (?,?,?,?)",
        rows
    )
    conn.commit()
    conn.close()


if __name__ == "__main__":
    build_manufacturer_db()
    build_distributor_db()
    build_vendor_db()
    build_consumer_affairs_db()
    print("4 isolated source databases created in ./data/:")
    for f in ["manufacturer.db", "distributor.db", "vendor.db", "consumer_affairs.db"]:
        print(" -", f)
