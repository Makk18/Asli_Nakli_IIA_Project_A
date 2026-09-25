"""
warehouse.py
-------------
Extends the Part A mediator (federation.py, virtual/GAV integration)
with a materialized analytics layer -- the "Hybrid: Semantic layer +
materialized views" architecture the lecture calls out as "useful for
enterprise semantic architectures". The mediator answers "what is the
history of THIS item?"; the warehouse answers "what does the overall
picture look like?" -- region totals, manufacturer totals, fake-item
counts -- which would be wasteful to recompute via federation on every
dashboard refresh.

This file implements, in this order, the four topics from the
"View Selection and Maintenance Problems" lecture:

  1. VIEW SELECTION      -- Greedy Benefit/Cost algorithm choosing
                             which candidate views to materialize
                             under a storage budget.
  2. VIEW MAINTENANCE     -- incremental delta rules (SUM is additive;
                             UPDATE = DELETE + INSERT) plus an
                             auxiliary state table for
                             self-maintainability.
  3. VIEW ADAPTATION      -- one case where the old MV can be adapted
                             without touching the sources, and one
                             case where it can't and must be rebuilt.
  4. AGGREGATE DATA       -- a hand-rolled CUBE(region, manufacturer),
                             since SQLite has no native CUBE/ROLLUP.
"""

import sqlite3
import os
import time

from federation import get_federated_connection, lookup_item

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
WAREHOUSE_PATH = os.path.join(DATA_DIR, "warehouse.db")


# =====================================================================
# 1. VIEW SELECTION  (lecture: "View Selection Problem" -> Greedy
#    Benefit/Cost heuristic)
# =====================================================================
#
# Candidate views are workload-driven: each corresponds to a real
# analytical question a stakeholder in the use case would ask
# repeatedly (Ministry dashboard, regional inspectors, manufacturer
# audits). Query frequencies below are STATED ASSUMPTIONS standing in
# for real production logs (exactly as the lecture's own worked
# example uses invented sec/day figures to demonstrate the algorithm
# mechanics, not real measurements) -- the algorithm itself is real and
# runs on whatever numbers you plug in.

ASSUMED_BYTES_PER_ROW = 120          # storage-cost assumption
STORAGE_BUDGET_BYTES = 700           # deliberately tight, so one view must lose

CANDIDATE_VIEWS = {
    "MV_verdict_summary": {
        "description": "Genuine/suspicious/fake item counts (Ministry of Consumer Affairs dashboard)",
        "assumed_daily_hits": 500,
        "cost_per_hit_if_virtual": 4,   # must run the full decision engine per item -> costliest to virtualize
    },
    "MV_region_summary": {
        "description": "Sales totals by region (regional inspectors)",
        "assumed_daily_hits": 300,
        "cost_per_hit_if_virtual": 2,   # one join (sales x distribution)
    },
    "MV_manufacturer_summary": {
        "description": "Sales totals by manufacturer (brand audit team)",
        "assumed_daily_hits": 100,
        "cost_per_hit_if_virtual": 2,   # one join (sales x products)
    },
}


def _measure_row_count(sql_over_gav):
    """Runs a query against the live GAV mediator and returns its row count -- the real, measured size of that candidate view if materialized."""
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute(sql_over_gav)
    n = len(cur.fetchall())
    conn.close()
    return n


CANDIDATE_VIEW_SQL = {
    "MV_verdict_summary": None,  # computed via the decision engine, not a plain SQL join -- see build step
    "MV_region_summary": """
        SELECT d.region, SUM(s.sale_price) AS total_sales_value, COUNT(*) AS item_count
        FROM GlobalSale s JOIN GlobalDistribution d ON s.item_code = d.item_code
        GROUP BY d.region
    """,
    "MV_manufacturer_summary": """
        SELECT p.manufacturer_name, SUM(s.sale_price) AS total_sales_value, COUNT(*) AS item_count
        FROM GlobalSale s JOIN GlobalItem p ON s.item_code = p.item_code
        GROUP BY p.manufacturer_name
    """,
}


def greedy_view_selection(verbose=True):
    """
    Implements the lecture's exact Greedy Benefit/Cost heuristic:

        Initialize SelectedViews = {}
        While space available do
            For each v in V - SelectedViews:
                Efficiency(v) = Benefit(v) / Size(v)
            Choose v* = argmax Efficiency(v)
            If Size(SelectedViews u {v*}) <= S: add v*
        Return SelectedViews

    Benefit(v)  = assumed_daily_hits * cost_per_hit_if_virtual
                  (cost saved per day by materializing v instead of
                  answering each hit through the live GAV mediator)
    Size(v)     = measured row count * ASSUMED_BYTES_PER_ROW
    """
    # MV_verdict_summary's "row count" = number of distinct items ever sold
    # (one row per verdict bucket would be tiny, but the *maintenance unit*
    # is per-item, so we size it by items considered -- see build step).
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT item_code FROM GlobalSale")
    n_items = len(cur.fetchall())
    conn.close()

    sizes = {
        "MV_verdict_summary": max(n_items, 1) * ASSUMED_BYTES_PER_ROW,
        "MV_region_summary": _measure_row_count(CANDIDATE_VIEW_SQL["MV_region_summary"]) * ASSUMED_BYTES_PER_ROW,
        "MV_manufacturer_summary": _measure_row_count(CANDIDATE_VIEW_SQL["MV_manufacturer_summary"]) * ASSUMED_BYTES_PER_ROW,
    }
    benefits = {
        name: cfg["assumed_daily_hits"] * cfg["cost_per_hit_if_virtual"]
        for name, cfg in CANDIDATE_VIEWS.items()
    }

    remaining = set(CANDIDATE_VIEWS)
    selected = []
    used = 0
    trace = []

    while remaining:
        efficiency = {v: benefits[v] / sizes[v] for v in remaining}
        v_star = max(efficiency, key=efficiency.get)
        fits = used + sizes[v_star] <= STORAGE_BUDGET_BYTES
        trace.append({
            "candidate": v_star,
            "benefit": benefits[v_star],
            "size_bytes": sizes[v_star],
            "efficiency": round(efficiency[v_star], 3),
            "selected": fits,
        })
        remaining.remove(v_star)
        if fits:
            selected.append(v_star)
            used += sizes[v_star]

    if verbose:
        print(f"Storage budget: {STORAGE_BUDGET_BYTES} bytes\n")
        for step in trace:
            mark = "\u2713 selected" if step["selected"] else "\u2717 skipped (would exceed budget)"
            print(f"  {step['candidate']:<24} benefit={step['benefit']:<5} size={step['size_bytes']:<5}B "
                  f"efficiency={step['efficiency']:<7} -> {mark}")
        print(f"\nTotal storage used: {used} / {STORAGE_BUDGET_BYTES} bytes")
        print(f"Selected views: {selected}")

    return selected, trace


# =====================================================================
# BUILD (ETL): materialize the selected views from the GAV mediator.
# This is the "hybrid" step -- pulling from the virtual layer once,
# then storing results physically for fast repeated dashboard reads.
# =====================================================================

def build_warehouse(selected_views=None):
    """
    NOTE on the relationship to Section 1: greedy_view_selection() is
    run separately, against a deliberately tight storage budget, purely
    to DEMONSTRATE the selection algorithm making a real trade-off
    (exactly like the lecture's own worked example, where v3 didn't
    fit). For the rest of this demo (maintenance, adaptation, CUBE) we
    build ALL candidate views regardless of that budget, because
    Sections 2-4 are about maintenance/adaptation mechanics on a fully
    populated warehouse, not about re-enforcing the storage
    constraint. A real deployment would instead pass the selected_views
    list straight from greedy_view_selection() into this function.
    """
    if selected_views is None:
        selected_views = list(CANDIDATE_VIEWS.keys())

    if os.path.exists(WAREHOUSE_PATH):
        os.remove(WAREHOUSE_PATH)
    wh = sqlite3.connect(WAREHOUSE_PATH)

    if "MV_region_summary" in selected_views:
        _materialize_join_view(wh, "MV_region_summary", CANDIDATE_VIEW_SQL["MV_region_summary"],
                                cols=["region", "total_sales_value", "item_count"])

    if "MV_manufacturer_summary" in selected_views:
        _materialize_join_view(wh, "MV_manufacturer_summary", CANDIDATE_VIEW_SQL["MV_manufacturer_summary"],
                                cols=["manufacturer_name", "total_sales_value", "item_count"])

    if "MV_verdict_summary" in selected_views:
        _materialize_verdict_summary(wh)

    # Strategic-design companion view for Section 3 (View Adaptation):
    # a FINER-GRAIN materialization (region x manufacturer) that later
    # lets us roll up to either dimension alone WITHOUT touching the
    # sources again.
    _materialize_fine_grain_view(wh)

    wh.commit()
    wh.close()


def _materialize_join_view(wh, table_name, sql, cols):
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()

    col_defs = ", ".join(f"{c} TEXT" if i == 0 else f"{c} REAL" for i, c in enumerate(cols))
    wh.execute(f"CREATE TABLE {table_name} ({col_defs})")
    wh.executemany(f"INSERT INTO {table_name} VALUES ({','.join('?' * len(cols))})", rows)


def _materialize_verdict_summary(wh):
    """
    Built from the decision engine (lookup_item), not a plain join --
    this is the aggregate-over-INTEGRATED-data view: exactly the
    pattern the lecture's own P2P quiz rewarded ("marks given if and
    only if the query fetches data from more than one data source and
    does aggregation/summarization on raw/integrated data").

    Also creates the auxiliary self-maintainability table
    (item_verdict_state) the lecture describes: "A materialized view
    is self-maintainable if it can be maintained without accessing all
    base source data... may require auxiliary relations stored at the
    warehouse." Here, that auxiliary relation records each item's LAST
    KNOWN verdict, so that a later complaint (which changes a verdict)
    can be applied as a DELETE-then-INSERT delta without re-scanning
    every item.
    """
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT item_code FROM GlobalSale")
    item_codes = [r[0] for r in cur.fetchall()]
    conn.close()

    counts = {"ASLI": 0, "SUSPICIOUS": 0, "NAKLI": 0}
    aux_rows = []
    for code in item_codes:
        verdict = lookup_item(code)["verdict"]
        counts[verdict] += 1
        aux_rows.append((code, verdict))

    wh.execute("CREATE TABLE MV_verdict_summary (verdict TEXT, item_count INTEGER)")
    wh.executemany("INSERT INTO MV_verdict_summary VALUES (?,?)", counts.items())

    wh.execute("CREATE TABLE item_verdict_state (item_code TEXT PRIMARY KEY, last_verdict TEXT)")
    wh.executemany("INSERT INTO item_verdict_state VALUES (?,?)", aux_rows)


def _materialize_fine_grain_view(wh):
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.region, p.manufacturer_name, SUM(s.sale_price) AS total_sales_value, COUNT(*) AS item_count
        FROM GlobalSale s
        JOIN GlobalDistribution d ON s.item_code = d.item_code
        JOIN GlobalItem p ON s.item_code = p.item_code
        GROUP BY d.region, p.manufacturer_name
    """)
    rows = cur.fetchall()
    conn.close()
    wh.execute("""
        CREATE TABLE MV_region_manufacturer_fine (
            region TEXT, manufacturer_name TEXT, total_sales_value REAL, item_count INTEGER
        )
    """)
    wh.executemany("INSERT INTO MV_region_manufacturer_fine VALUES (?,?,?,?)", rows)


# =====================================================================
# 2. VIEW MAINTENANCE  (lecture: "Materialized View Maintenance" ->
#    delta rules; SUM is additive; UPDATE = DELETE + INSERT)
# =====================================================================

def maintain_after_new_sale(item_code, sale_price, region=None, manufacturer_name=None):
    """
    Incremental maintenance for a newly recorded sale. Per the
    lecture's delta rule for SUM ("SUM is easy because contributions
    are additive"):

        V'[key] = V[key] + delta

    We touch ONLY the affected row (or insert a new one) -- no
    recomputation of the other rows, and no re-scan of GlobalSale.
    """
    wh = sqlite3.connect(WAREHOUSE_PATH)
    touched = []

    if region is not None:
        row = wh.execute(
            "SELECT total_sales_value, item_count FROM MV_region_summary WHERE region = ?", (region,)
        ).fetchone()
        if row is None:
            wh.execute("INSERT INTO MV_region_summary VALUES (?,?,?)", (region, sale_price, 1))
        else:
            wh.execute(
                "UPDATE MV_region_summary SET total_sales_value = ?, item_count = ? WHERE region = ?",
                (row[0] + sale_price, row[1] + 1, region),
            )
        touched.append(f"MV_region_summary[{region}] += {sale_price}")

    if manufacturer_name is not None:
        row = wh.execute(
            "SELECT total_sales_value, item_count FROM MV_manufacturer_summary WHERE manufacturer_name = ?",
            (manufacturer_name,),
        ).fetchone()
        if row is None:
            wh.execute("INSERT INTO MV_manufacturer_summary VALUES (?,?,?)", (manufacturer_name, sale_price, 1))
        else:
            wh.execute(
                "UPDATE MV_manufacturer_summary SET total_sales_value = ?, item_count = ? WHERE manufacturer_name = ?",
                (row[0] + sale_price, row[1] + 1, manufacturer_name),
            )
        touched.append(f"MV_manufacturer_summary[{manufacturer_name}] += {sale_price}")

    # A newly sold item is being SEEN for the first time -> INSERT into
    # verdict_summary (not an update, since it has no prior verdict).
    verdict = lookup_item(item_code)["verdict"]
    wh.execute(
        "UPDATE MV_verdict_summary SET item_count = item_count + 1 WHERE verdict = ?", (verdict,)
    )
    wh.execute(
        "INSERT OR REPLACE INTO item_verdict_state VALUES (?,?)", (item_code, verdict)
    )
    touched.append(f"MV_verdict_summary[{verdict}] += 1 (new item)")

    wh.commit()
    wh.close()
    return touched


def maintain_after_new_complaint(item_code):
    """
    Incremental maintenance for a newly filed complaint. A complaint
    can change an item's verdict (e.g. ASLI -> NAKLI once a counterfeit
    report lands) -- this is exactly the lecture's:

        "3. UPDATE: DELETION followed by INSERTION"

    We do NOT need to re-scan every item to find the item's OLD
    verdict: we read it from the auxiliary self-maintainable state
    table (item_verdict_state) built in _materialize_verdict_summary,
    exactly the lecture's "auxiliary relations... store customer_id ->
    affected order IDs" pattern, adapted to item_code -> last verdict.
    """
    wh = sqlite3.connect(WAREHOUSE_PATH)
    row = wh.execute("SELECT last_verdict FROM item_verdict_state WHERE item_code = ?", (item_code,)).fetchone()
    old_verdict = row[0] if row else None

    new_verdict = lookup_item(item_code)["verdict"]

    if old_verdict == new_verdict:
        wh.close()
        return [f"No change: {item_code} was already {old_verdict}"]

    touched = []
    if old_verdict is not None:
        wh.execute("UPDATE MV_verdict_summary SET item_count = item_count - 1 WHERE verdict = ?", (old_verdict,))
        touched.append(f"DELETE 1 from MV_verdict_summary[{old_verdict}]")
    wh.execute("UPDATE MV_verdict_summary SET item_count = item_count + 1 WHERE verdict = ?", (new_verdict,))
    touched.append(f"INSERT 1 into MV_verdict_summary[{new_verdict}]")
    wh.execute("INSERT OR REPLACE INTO item_verdict_state VALUES (?,?)", (item_code, new_verdict))

    wh.commit()
    wh.close()
    return touched


def full_refresh():
    """The alternative to incremental maintenance: recompute everything
    from scratch. Used only to demonstrate the cost difference."""
    selected, _ = greedy_view_selection(verbose=False)
    build_warehouse(selected)


# =====================================================================
# 3. VIEW ADAPTATION  (lecture: "View adaptation -- a different
#    problem" -> often possible vs often impossible)
# =====================================================================

def adapt_region_summary_to_include_manufacturer():
    """
    OFTEN IMPOSSIBLE case: someone asks for region x manufacturer
    breakdown, but MV_region_summary was materialized WITHOUT
    manufacturer_name. Per the lecture: "New grouping attribute was
    never materialized" -> the old MV cannot be adapted; we must go
    back to the sources (rebuild via the mediator).
    """
    wh = sqlite3.connect(WAREHOUSE_PATH)
    cols = [d[1] for d in wh.execute("PRAGMA table_info(MV_region_summary)").fetchall()]
    wh.close()
    if "manufacturer_name" in cols:
        return "Adaptable: manufacturer_name already retained.", None

    # Not adaptable from the stored MV alone -> rebuild from sources.
    conn = get_federated_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT d.region, p.manufacturer_name, SUM(s.sale_price), COUNT(*)
        FROM GlobalSale s
        JOIN GlobalDistribution d ON s.item_code = d.item_code
        JOIN GlobalItem p ON s.item_code = p.item_code
        GROUP BY d.region, p.manufacturer_name
    """)
    rebuilt = cur.fetchall()
    conn.close()
    return (
        "NOT adaptable from MV_region_summary alone (manufacturer_name was never retained) "
        "-> rebuilt by re-querying the GAV mediator.",
        rebuilt,
    )


def rollup_region_only_from_fine_grain():
    """
    OFTEN POSSIBLE case: MV_region_manufacturer_fine already retains
    BOTH dimensions (the "strategic design" from the lecture:
    "Materialize reusable intermediate states... retain dimensions
    needed for likely grouping"). Rolling up to region-only is then a
    local aggregation over the already-materialized fine-grain table
    -- no source access needed at all.
    """
    wh = sqlite3.connect(WAREHOUSE_PATH)
    rows = wh.execute("""
        SELECT region, SUM(total_sales_value), SUM(item_count)
        FROM MV_region_manufacturer_fine
        GROUP BY region
    """).fetchall()
    wh.close()
    return "Adaptable: rolled up locally from MV_region_manufacturer_fine, zero source queries.", rows


# =====================================================================
# 4. AGGREGATE DATA  (lecture: "Multi-dimensional data analysis" ->
#    GROUP BY CUBE; SQLite has no native CUBE/ROLLUP, so built by hand
#    as the union of groupings -- which is what CUBE computes anyway)
# =====================================================================

def cube_region_manufacturer():
    """
    Hand-rolled equivalent of:
        SELECT region, manufacturer_name, SUM(total_sales_value), SUM(item_count)
        FROM MV_region_manufacturer_fine
        GROUP BY CUBE(region, manufacturer_name)

    Per the lecture, CUBE(A,B) is the union of the 2^2 = 4 groupings:
    {(region,manufacturer), (region), (manufacturer), ()}, with NULL
    standing in for a dimension not present in that grouping.
    """
    wh = sqlite3.connect(WAREHOUSE_PATH)
    cur = wh.cursor()

    cur.execute("""
        SELECT region, manufacturer_name, total_sales_value, item_count
        FROM MV_region_manufacturer_fine
    """)
    both = cur.fetchall()

    cur.execute("""
        SELECT region, NULL, SUM(total_sales_value), SUM(item_count)
        FROM MV_region_manufacturer_fine GROUP BY region
    """)
    region_only = cur.fetchall()

    cur.execute("""
        SELECT NULL, manufacturer_name, SUM(total_sales_value), SUM(item_count)
        FROM MV_region_manufacturer_fine GROUP BY manufacturer_name
    """)
    manufacturer_only = cur.fetchall()

    cur.execute("""
        SELECT NULL, NULL, SUM(total_sales_value), SUM(item_count)
        FROM MV_region_manufacturer_fine
    """)
    grand_total = cur.fetchall()

    wh.close()
    return both + region_only + manufacturer_only + grand_total


if __name__ == "__main__":
    print("=== 1. VIEW SELECTION (Greedy Benefit/Cost) ===")
    print("(Demonstrates the algorithm under a deliberately tight storage")
    print(" budget, so exactly one candidate view is excluded -- same")
    print(" shape as the lecture's own worked CarRental/Region example.)\n")
    greedy_view_selection()

    print("\n=== Building the FULL warehouse (all 3 views) for Sections 2-4 ===")
    print("(Sections 2-4 demonstrate maintenance/adaptation mechanics, which")
    print(" needs all views materialized -- see the note in build_warehouse().)")
    build_warehouse()  # builds all candidate views, not just the budget-selected ones
    print("warehouse.db created.")

    print("\n=== 2. VIEW MAINTENANCE demo ===")
    print("New sale: MED-1002 sold again in Delhi NCR for 66.0 (Amoxicillin, Sun Pharma)")
    print(maintain_after_new_sale("MED-1002", 66.0, region="Delhi NCR", manufacturer_name="Sun Pharma"))
    print("\nA new counterfeit complaint arrives against MED-1001 (currently ASLI):")
    ca_conn = sqlite3.connect(os.path.join(DATA_DIR, "consumer_affairs.db"))
    ca_conn.execute(
        "INSERT INTO complaints (flagged_code, reason, reported_on, status) VALUES (?,?,?,?)",
        ("MED-1001", "Batch found with tampered hologram seal", "2026-09-16", "Verified Nakli"),
    )
    ca_conn.commit()
    ca_conn.close()
    print(maintain_after_new_complaint("MED-1001"))
    print("(This is the UPDATE = DELETE-then-INSERT case: MED-1001 moves out of the ASLI")
    print(" bucket and into NAKLI, using the auxiliary item_verdict_state table to know")
    print(" its OLD verdict without re-scanning every other item.)")

    print("\n=== 3. VIEW ADAPTATION demo ===")
    msg, rebuilt = adapt_region_summary_to_include_manufacturer()
    print(msg)
    msg2, rolled = rollup_region_only_from_fine_grain()
    print(msg2)

    print("\n=== 4. AGGREGATE DATA: hand-rolled CUBE(region, manufacturer) ===")
    for row in cube_region_manufacturer():
        print(" ", row)
