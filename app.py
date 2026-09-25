"""
app.py
------
Integrated GUI for Asli ya Nakli:
  - Tab 1: Item Lookup (Part A: GAV/Federation mediator)
  - Tab 2: Decision Engine (Innovative decision-making rule engine walkthrough & live trace)
  - Tab 3: SQL Query Console (Run ANY arbitrary SQL query across any source or federated mediator)
  - Tab 4: Manual Data Entry (Add new records directly to source databases)
  - Tab 5: Analytics Warehouse (DWH extension: view selection, maintenance, adaptation, CUBE)

Run with:  streamlit run app.py
"""

import streamlit as st
from federation import lookup_item, get_federated_connection, decide_step_by_step
import os
import sqlite3
import pandas as pd
import datetime
import warehouse
from logger import log_event, get_logs, clear_logs
from qr_utils import decode_qr, generate_qr_image
import geo_analytics
from streamlit_folium import st_folium

st.set_page_config(page_title="Asli ya Nakli? - Multi-DB Federation & DWH", page_icon="🛡️", layout="wide")

data_dir = os.path.join(os.path.dirname(__file__), "data")
if not os.path.exists(os.path.join(data_dir, "manufacturer.db")):
    st.error("Source databases not found. Run `python setup_sources.py` first.")
    st.stop()

# Define tabs
tab_lookup, tab_decision, tab_sql, tab_entry, tab_warehouse, tab_heatmap, tab_logs = st.tabs([
    "🔍 Item Lookup & QR Scanner",
    "🧠 Decision Engine (Innovative Core)",
    "💻 SQL Query Console",
    "📝 Manual Data Entry & QR Generator",
    "📊 Analytics Warehouse (DWH)",
    "🗺️ Geospatial Risk Heatmap",
    "📜 Process & System Logs"
])

# =====================================================================
# SIDEBAR: 3-Laptop Distributed Cluster Monitor & IP Configuration
# =====================================================================
with st.sidebar:
    st.header("💻 3-Laptop Cluster Network")
    st.caption("Centralized GAV Mediator communicating across 3 laptops on Wi-Fi / Local Network:")

    from config import load_config, save_config
    from federation import check_all_nodes, get_remote_nodes

    cluster_cfg = load_config()

    # Expandable IP Configuration for the 3 Laptops
    with st.expander("⚙️ Configure Laptop IPs (Wi-Fi / LAN)", expanded=False):
        st.write("Enter the local IP address for each physical laptop:")

        new_l1_ip = st.text_input(
            "Laptop 1 (Manufacturer) IP:",
            value=cluster_cfg["laptop_1_mfr"].get("host", "127.0.0.1"),
            help="E.g., 192.168.1.10 or 127.0.0.1"
        )
        new_l2_ip = st.text_input(
            "Laptop 2 (Distributor) IP:",
            value=cluster_cfg["laptop_2_dist"].get("host", "127.0.0.1"),
            help="E.g., 192.168.1.11 or 127.0.0.1"
        )
        new_l3_ip = st.text_input(
            "Laptop 3 (Retail / Consumer) IP:",
            value=cluster_cfg["laptop_3_retail"].get("host", "127.0.0.1"),
            help="E.g., 192.168.1.12 or 127.0.0.1"
        )

        if st.button("💾 Save Laptop IPs", use_container_width=True):
            cluster_cfg["laptop_1_mfr"]["host"] = new_l1_ip.strip()
            cluster_cfg["laptop_2_dist"]["host"] = new_l2_ip.strip()
            cluster_cfg["laptop_3_retail"]["host"] = new_l3_ip.strip()
            save_config(cluster_cfg)
            st.success("Configuration saved!")
            st.rerun()

    st.divider()
    st.subheader("Live Node Connectivity")

    nodes_status = check_all_nodes()
    nodes_info = get_remote_nodes()

    laptop_cards = [
        ("💻 Laptop 1", "manufacturer", cluster_cfg["laptop_1_mfr"]["host"]),
        ("💻 Laptop 2", "distributor", cluster_cfg["laptop_2_dist"]["host"]),
        ("💻 Laptop 3", "vendor", cluster_cfg["laptop_3_retail"]["host"]),
    ]

    for label, node_key, host_ip in laptop_cards:
        st_res = nodes_status.get(node_key, {})
        n_info = nodes_info.get(node_key, {})
        online = st_res.get("online", False)

        if online:
            st.success(
                f"🟢 **{label}** ({n_info.get('name', '')})\n"
                f"- URL: `{st_res.get('url', '')}`\n"
                f"- Latency: `{st_res.get('latency_ms', 0)} ms`"
            )
        else:
            st.error(
                f"🔴 **{label}** ({n_info.get('name', '')})\n"
                f"- Target: `http://{host_ip}:5000`\n"
                f"- Status: `Offline (Local Fallback Active)`"
            )

    if st.button("🔄 Refresh Network Ping", use_container_width=True):
        st.rerun()

    st.divider()
    st.markdown("### 📋 3-Laptop Execution Commands")
    st.markdown(
        """
        - **On Laptop 1**:
          `python laptop_1_manufacturer.py`
        - **On Laptop 2**:
          `python laptop_2_distributor.py`
        - **On Laptop 3**:
          `python laptop_3_retail_and_consumer.py`
          `streamlit run app.py`
        """
    )



# =====================================================================
# TAB 1: Item Lookup & Live QR Scanner (Part A — GAV mediator / federation.py)
# =====================================================================
with tab_lookup:
    st.title("🔍 Asli ya Nakli — Item Verification & Live QR Scanner")
    st.caption(
        "Scan a medicine QR code with your webcam, upload an image, or enter an item code to verify its complete "
        "history across Manufacturer, Distributor, Vendor, and Consumer Affairs nodes via live GAV mediation."
    )

    # Input method selection
    input_method = st.radio(
        "Verification Input Method:",
        ["🔤 Manual Code / Sample Dropdown", "📷 Live Webcam QR Scanner", "📁 Upload QR Image"],
        horizontal=True
    )

    lookup_code = ""

    if input_method == "🔤 Manual Code / Sample Dropdown":
        col_m1, col_m2 = st.columns([1, 1])
        with col_m1:
            sample_codes = ["MED-1001", "MED-1002", "MED-1003", "MED-1004", "MED-1005", "MED-9999"]
            code = st.selectbox(
                "Select a sample code:",
                options=[""] + sample_codes,
                index=0,
                key="lookup_select"
            )
        with col_m2:
            manual = st.text_input("...or type any code directly:", key="lookup_manual")
        lookup_code = manual.strip() or code

    elif input_method == "📷 Live Webcam QR Scanner":
        st.write("Hold your medicine box or QR badge in front of your camera:")
        camera_photo = st.camera_input("Capture Medicine QR Code", key="camera_scan")
        if camera_photo:
            with st.spinner("Decoding QR code via computer vision..."):
                scanned_val, msg = decode_qr(camera_photo)
                if scanned_val:
                    st.success(f"🎯 **{msg}**")
                    lookup_code = scanned_val
                    log_event("SYSTEM", "Camera QR Scanned", f"Successfully decoded '{scanned_val}' from camera input", status="SUCCESS", node="Camera Scanner")
                else:
                    st.warning(f"⚠️ {msg}")

    elif input_method == "📁 Upload QR Image":
        uploaded_qr = st.file_uploader("Upload an image containing a medicine QR code / label:", type=["png", "jpg", "jpeg"], key="qr_file_upload")
        if uploaded_qr:
            with st.spinner("Analyzing image for QR code..."):
                scanned_val, msg = decode_qr(uploaded_qr)
                if scanned_val:
                    st.success(f"🎯 **{msg}**")
                    lookup_code = scanned_val
                    log_event("SYSTEM", "File QR Decoded", f"Decoded code '{scanned_val}' from uploaded file", status="SUCCESS", node="File Scanner")
                else:
                    st.warning(f"⚠️ {msg}")

    # Interactive Sample QR Badges for Quick Testing
    with st.expander("🏷️ Sample Anti-Counterfeit QR Stickers (Test directly on-screen or with webcam)"):
        st.caption("Point your camera at any QR code below, or click 'Test Scan' to immediately load and verify it:")
        qr_cols = st.columns(4)
        sample_tests = [
            ("MED-1001", "Paracetamol 500mg", "✅ Expected: ASLI"),
            ("MED-1002", "Amoxicillin 250mg", "✅ Expected: ASLI"),
            ("MED-1004", "Metformin 500mg", "⚠️ Expected: SUSPICIOUS"),
            ("MED-9999", "Counterfeit Fake", "❌ Expected: NAKLI"),
        ]
        for idx, (s_code, s_name, s_exp) in enumerate(sample_tests):
            with qr_cols[idx]:
                qr_buf = generate_qr_image(s_code, {"product": s_name})
                st.image(qr_buf, width=130, caption=f"{s_code}\n{s_exp}")
                if st.button(f"Scan {s_code}", key=f"btn_quick_scan_{s_code}", use_container_width=True):
                    lookup_code = s_code
                    st.session_state["active_scanned_code"] = s_code

    if "active_scanned_code" in st.session_state and not lookup_code:
        lookup_code = st.session_state["active_scanned_code"]

    col_chk_btn, col_chk_info = st.columns([1, 3])
    with col_chk_btn:
        check_triggered = st.button("🚀 Verify Item Provenance", type="primary", key="btn_check", use_container_width=True)

    # Auto-run if QR code was newly scanned or user clicked button
    if (check_triggered or (input_method != "🔤 Manual Code / Sample Dropdown" and lookup_code)) and lookup_code:
        st.session_state["active_scanned_code"] = lookup_code
        result = lookup_item(lookup_code)

        verdict = result["verdict"]
        color = {"ASLI": "green", "SUSPICIOUS": "orange", "NAKLI": "red"}[verdict]
        label = {"ASLI": "✅ ASLI (Genuine)", "SUSPICIOUS": "⚠️ SUSPICIOUS", "NAKLI": "❌ NAKLI (Fake)"}[verdict]

        st.markdown(f"## :{color}[{label}]")
        st.info(result["reason"])

        st.divider()
        st.subheader("Integrated Evidence Across All 4 Data Sources")

        sources_meta = result.get("sources_meta", {})
        def meta_badge(src_name):
            info = sources_meta.get(src_name, {})
            mode = info.get("mode", "local")
            laptop = info.get("laptop", "Local")
            url = info.get("url", "")
            if mode == "network":
                return f" :green[(📡 {laptop} Network Node : `{url}`)]"
            return f" :blue[(💾 Local Storage Fallback)]"

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"#### 🏭 Manufacturer Record (`manufacturer.db`){meta_badge('manufacturer')}")
            if result["manufacturer"]:
                st.json(result["manufacturer"])
            else:
                st.error("❌ No manufacturer record found — this code was never registered by any legitimate manufacturer.")

            st.markdown(f"#### 🛒 Vendor Point-of-Sale Scans (`vendor.db`){meta_badge('vendor')}")
            if result["sales"]:
                st.dataframe(pd.DataFrame(result["sales"]), use_container_width=True)
            else:
                st.info("ℹ️ No sale scans recorded for this code.")

        with col2:
            st.markdown(f"#### 🚚 Authorized Distribution Trail (`distributor.db`){meta_badge('distributor')}")
            if result["distribution"]:
                st.dataframe(pd.DataFrame(result["distribution"]), use_container_width=True)
            else:
                st.warning("⚠️ No authorised distributor ever dispatched this code.")

            st.markdown(f"#### 📋 Consumer Affairs Fraud Reports (`consumer_affairs.db`){meta_badge('consumer_affairs')}")
            if result["complaints"]:
                st.dataframe(pd.DataFrame(result["complaints"]), use_container_width=True)
            else:
                st.success("✅ No consumer complaints or fraud reports on file.")

        with st.expander("ℹ️ How was this computed? (GAV Mediation Architecture)"):
            st.markdown(
                """
This result was **not** looked up in one table. It was produced by:

1. **GAV schema mapping** — each source names the item code differently
   (`mfr_item_code`, `supplier_code`, `scanned_code`, `flagged_code`).
   Global relations (`GlobalItem`, `GlobalDistribution`, `GlobalSale`, `GlobalComplaint`)
   are defined as SQL views over sources.
2. **SQL federation** — all four SQLite databases are `ATTACH`ed into a single mediator connection,
   so one session queries across all of them without copying data.
3. **Decision rule over integrated evidence** — the ASLI / SUSPICIOUS / NAKLI verdict
   is computed by evaluating rules over the integrated data graph.
"""
            )


# =====================================================================
# TAB 2: Decision Engine (Innovative Decision Making in GUI)
# =====================================================================
with tab_decision:
    st.title("🧠 Innovative Decision Making Engine")
    st.markdown(
        """
        ### What is the Innovative Part of Decision Making?
        Traditional data integration systems simply produce a wider **joined table** (ETL / Federated union).
        **The innovative part here is automated provenance reasoning**:
        Instead of asking the human analyst to manually compare rows across 4 databases, our system synthesizes
        an authoritative, context-aware verdict (**ASLI**, **SUSPICIOUS**, or **NAKLI**) by checking
        **cross-source ontological integrity constraints** and **supply-chain provenance**.
        """
    )

    st.subheader("1. Provenance Decision Tree Flowchart")
    st.markdown(
        """
```mermaid
flowchart TD
    Start(["Item Code Scanned"]) --> R1{"Rule 1: Exists in Manufacturer DB?"}
    R1 -- "No (Unregistered code)" --> Nakli1["❌ NAKLI (Fake Product)<br>Never registered by legitimate manufacturer"]
    R1 -- "Yes" --> R2{"Rule 2: Verified Nakli Complaint on file?"}
    R2 -- "Yes (Official Fraud Report)" --> Nakli2["❌ NAKLI (Counterfeit Confirmed)<br>Flagged by Consumer Affairs"]
    R2 -- "No" --> R3{"Rule 3: Exists in Distributor Dispatch Trail?"}
    R3 -- "No (Broken supply chain)" --> Suspicious["⚠️ SUSPICIOUS (Diverted / Grey Market)<br>Valid mfr code but bypassed authorized distribution"]
    R3 -- "Yes" --> Asli["✅ ASLI (Genuine & Authorized)<br>Valid Mfr + Authorized Trail + Clean Record"]

    classDef red fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c;
    classDef orange fill:#fff3e0,stroke:#ef6c00,stroke-width:2px,color:#e65100;
    classDef green fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef step fill:#e3f2fd,stroke:#1565c0,stroke-width:1px,color:#0d47a1;

    class Nakli1,Nakli2 red;
    class Suspicious orange;
    class Asli green;
    class R1,R2,R3,Start step;
```
"""
    )

    st.divider()
    st.subheader("2. Live Interactive Rule Execution Trace")
    st.write("Pick any item to step through the decision rules dynamically with live evaluation:")

    dec_sample_codes = ["MED-1001", "MED-1002", "MED-1003", "MED-1004", "MED-1005", "MED-9999"]
    dec_code = st.selectbox("Select Code for Provenance Trace:", dec_sample_codes, key="dec_code_select")
    custom_dec = st.text_input("Or enter a custom code to test:", key="dec_code_custom")
    eval_code = custom_dec.strip() or dec_code

    if st.button("Run Decision Engine Analysis", type="primary", key="btn_run_decision"):
        steps, final_verdict, final_reason = decide_step_by_step(eval_code)

        v_color = {"ASLI": "green", "SUSPICIOUS": "orange", "NAKLI": "red"}[final_verdict]
        v_badge = {"ASLI": "✅ ASLI (Genuine)", "SUSPICIOUS": "⚠️ SUSPICIOUS", "NAKLI": "❌ NAKLI (Fake)"}[final_verdict]

        st.markdown(f"### Final Verdict: :{v_color}[{v_badge}]")
        st.write(f"**Conclusion:** {final_reason}")

        st.markdown("#### Step-by-Step Rule Traversal:")

        for s in steps:
            fired = s["fired"]
            with st.container():
                cols = st.columns([1, 4, 2])
                with cols[0]:
                    if fired:
                        st.markdown(f"### 🛑 Rule {s['rule_no']}")
                        st.caption("🚨 **TRIGGERED**" if s['verdict'] else "🏁 **PASSED**")
                    else:
                        st.markdown(f"### ⏭️ Rule {s['rule_no']}")
                        st.caption("✅ Condition Not Met (Proceed)")

                with cols[1]:
                    st.markdown(f"**{s['rule_name']}**")
                    st.markdown(f"• **Tested Condition:** `{s['condition']}`")
                    st.markdown(f"• **Data Source Evaluated:** `{s['source']}`")
                    if s["fired"] and s["reason"]:
                        st.warning(f"**Action Taken:** {s['reason']}")

                with cols[2]:
                    with st.expander("Inspected Evidence", expanded=fired):
                        st.write(s["evidence"])

                st.divider()


# =====================================================================
# TAB 3: SQL Query Console (Run ANY SQL on ANY Database or Mediator)
# =====================================================================
with tab_sql:
    st.title("💻 Live SQL Query Console")
    st.caption(
        "Execute ANY SQL query (SELECT, INSERT, UPDATE, DELETE) against the federated mediator "
        "or individual source databases directly in the GUI."
    )

    db_options = {
        "🌐 Federated In-Memory Mediator (GAV Global Views + All 4 Sources Attached)": "federation",
        "🏭 manufacturer.db (Products & Mfr details)": os.path.join(data_dir, "manufacturer.db"),
        "🚚 distributor.db (Supply chain dispatches)": os.path.join(data_dir, "distributor.db"),
        "🛒 vendor.db (Point of sale scanned purchases)": os.path.join(data_dir, "vendor.db"),
        "📋 consumer_affairs.db (Fraud complaints & status)": os.path.join(data_dir, "consumer_affairs.db"),
        "📊 warehouse.db (Materialized views / OLAP)": warehouse.WAREHOUSE_PATH
    }

    selected_db_label = st.selectbox("Select Target Database:", list(db_options.keys()))
    selected_target = db_options[selected_db_label]

    # Schema Explorer in Expander
    with st.expander("📂 Schema Explorer (Inspect available tables and columns)"):
        try:
            if selected_target == "federation":
                conn_tmp = get_federated_connection()
            else:
                if not os.path.exists(selected_target):
                    st.warning(f"Database file not created yet: {selected_target}")
                    conn_tmp = None
                else:
                    conn_tmp = sqlite3.connect(selected_target)

            if conn_tmp:
                cur = conn_tmp.cursor()
                tables = cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'").fetchall()
                if not tables:
                    st.write("No tables or views found.")
                for tbl_name, tbl_type in tables:
                    cols = cur.execute(f"PRAGMA table_info('{tbl_name}')").fetchall()
                    col_str = ", ".join([f"{c[1]} ({c[2]})" for c in cols])
                    st.markdown(f"- **{tbl_name}** `[{tbl_type.upper()}]`: `{col_str}`")
                conn_tmp.close()
        except Exception as e:
            st.error(f"Error exploring schema: {e}")

    # Presets / Quick Query Templates based on selected DB
    st.markdown("#### Quick Query Templates:")
    preset_cols = st.columns(4)

    if selected_target == "federation":
        with preset_cols[0]:
            if st.button("GlobalItem (Federated)", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM GlobalItem;"
        with preset_cols[1]:
            if st.button("Cross-Source Join (GAV)", use_container_width=True):
                st.session_state["sql_input"] = (
                    "SELECT p.item_code, p.item_name, d.distributor_name, s.sale_price, c.status\n"
                    "FROM GlobalItem p\n"
                    "LEFT JOIN GlobalDistribution d ON p.item_code = d.item_code\n"
                    "LEFT JOIN GlobalSale s ON p.item_code = s.item_code\n"
                    "LEFT JOIN GlobalComplaint c ON p.item_code = c.item_code;"
                )
        with preset_cols[2]:
            if st.button("Count by Manufacturer", use_container_width=True):
                st.session_state["sql_input"] = (
                    "SELECT manufacturer_name, COUNT(*) AS count, AVG(mrp) AS avg_mrp\n"
                    "FROM GlobalItem\n"
                    "GROUP BY manufacturer_name;"
                )
        with preset_cols[3]:
            if st.button("Supply-Chain Leakage", use_container_width=True):
                st.session_state["sql_input"] = (
                    "SELECT s.item_code, p.item_name, s.vendor_id\n"
                    "FROM GlobalSale s JOIN GlobalItem p ON s.item_code = p.item_code\n"
                    "LEFT JOIN GlobalDistribution d ON s.item_code = d.item_code\n"
                    "WHERE d.item_code IS NULL;"
                )
        default_suggestion = "SELECT * FROM GlobalItem LIMIT 10;"
    elif "manufacturer.db" in selected_target:
        with preset_cols[0]:
            if st.button("All Products", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM products;"
        with preset_cols[1]:
            if st.button("Filter by Manufacturer", use_container_width=True):
                st.session_state["sql_input"] = "SELECT mfr_item_code, item_name, mrp FROM products WHERE manufacturer_name = 'Cipla Ltd';"
        with preset_cols[2]:
            if st.button("High MRP Products", use_container_width=True):
                st.session_state["sql_input"] = "SELECT mfr_item_code, item_name, mrp FROM products WHERE mrp > 30.0;"
        with preset_cols[3]:
            if st.button("Count Products", use_container_width=True):
                st.session_state["sql_input"] = "SELECT manufacturer_name, COUNT(*) FROM products GROUP BY manufacturer_name;"
        default_suggestion = "SELECT * FROM products;"
    elif "distributor.db" in selected_target:
        with preset_cols[0]:
            if st.button("All Dispatches", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM distribution;"
        with preset_cols[1]:
            if st.button("Volume by Region", use_container_width=True):
                st.session_state["sql_input"] = "SELECT region, SUM(qty) AS total_units FROM distribution GROUP BY region;"
        with preset_cols[2]:
            if st.button("Shipments by Distributor", use_container_width=True):
                st.session_state["sql_input"] = "SELECT distributor_name, COUNT(*) FROM distribution GROUP BY distributor_name;"
        with preset_cols[3]:
            if st.button("Delhi NCR Dispatches", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM distribution WHERE region = 'Delhi NCR';"
        default_suggestion = "SELECT * FROM distribution;"
    elif "vendor.db" in selected_target:
        with preset_cols[0]:
            if st.button("All Scanned Sales", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM sales;"
        with preset_cols[1]:
            if st.button("Sales by Vendor ID", use_container_width=True):
                st.session_state["sql_input"] = "SELECT vendor_id, COUNT(*), SUM(sale_price) FROM sales GROUP BY vendor_id;"
        with preset_cols[2]:
            if st.button("Highest Value Sales", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM sales ORDER BY sale_price DESC;"
        with preset_cols[3]:
            if st.button("Roadside Kiosk Sales", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM sales WHERE vendor_id = 'Roadside Kiosk';"
        default_suggestion = "SELECT * FROM sales;"
    elif "consumer_affairs.db" in selected_target:
        with preset_cols[0]:
            if st.button("All Fraud Reports", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM complaints;"
        with preset_cols[1]:
            if st.button("Verified Counterfeits", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM complaints WHERE status = 'Verified Nakli';"
        with preset_cols[2]:
            if st.button("Under Investigation", use_container_width=True):
                st.session_state["sql_input"] = "SELECT * FROM complaints WHERE status = 'Under Investigation';"
        with preset_cols[3]:
            if st.button("Complaints Count", use_container_width=True):
                st.session_state["sql_input"] = "SELECT status, COUNT(*) FROM complaints GROUP BY status;"
        default_suggestion = "SELECT * FROM complaints;"
    else:
        default_suggestion = "SELECT * FROM MV_region_summary;"

    # If user changed database, auto-switch default query
    if "last_selected_db" not in st.session_state or st.session_state["last_selected_db"] != selected_target:
        st.session_state["last_selected_db"] = selected_target
        st.session_state["sql_input"] = default_suggestion

    default_sql = st.session_state.get("sql_input", default_suggestion)
    sql_query = st.text_area("SQL Query Editor:", value=default_sql, height=140, key="sql_editor")

    col_btn, col_help = st.columns([1, 4])
    with col_btn:
        run_query = st.button("▶️ Execute Query", type="primary", use_container_width=True)

    if run_query and sql_query.strip():
        try:
            query_clean = sql_query.strip()
            is_select = (
                query_clean.upper().startswith("SELECT")
                or query_clean.upper().startswith("PRAGMA")
                or query_clean.upper().startswith("EXPLAIN")
            )

            is_federation = (selected_target == "federation")
            if is_federation:
                conn = get_federated_connection()
            else:
                if not os.path.exists(selected_target):
                    st.error(f"Database file does not exist: {selected_target}")
                    st.stop()
                conn = sqlite3.connect(selected_target)

            cur = conn.cursor()

            # Check if selected target corresponds to a distributed network node
            node_key_mapping = {
                os.path.join(data_dir, "manufacturer.db"): "manufacturer",
                os.path.join(data_dir, "distributor.db"): "distributor",
                os.path.join(data_dir, "vendor.db"): "vendor",
                os.path.join(data_dir, "consumer_affairs.db"): "consumer_affairs"
            }
            node_key = node_key_mapping.get(selected_target)

            if is_select:
                if node_key:
                    from federation import query_remote_node
                    q_res = query_remote_node(node_key, query_clean)
                    df = pd.DataFrame(q_res["rows"], columns=q_res["columns"])
                    laptop_tag = q_res.get("laptop", "Remote Node")
                    url_tag = q_res.get("url", "")
                    src_tag = f"📡 {laptop_tag} (`{url_tag}`)" if q_res["source"] == "network" else "💾 Local Storage Fallback"
                    st.success(f"Query returned {len(df)} row(s) via {src_tag}.")
                    st.dataframe(df, use_container_width=True)
                    log_event("SQL_QUERY", f"Remote SELECT ({node_key})", f"Query on {laptop_tag}: {query_clean[:80]} | Returned {len(df)} row(s)", status="SUCCESS", node=laptop_tag)
                else:
                    cur.execute(query_clean)
                    rows = cur.fetchall()
                    cols = [desc[0] for desc in cur.description] if cur.description else []
                    df = pd.DataFrame(rows, columns=cols)
                    st.success(f"Query returned {len(df)} row(s) via Federated Mediator.")
                    st.dataframe(df, use_container_width=True)
                    log_event("SQL_QUERY", "Federated SELECT (GAV)", f"Executed across mediator: {query_clean[:80]} | Returned {len(df)} row(s)", status="SUCCESS", node="Mediator")
            else:
                if node_key:
                    from federation import execute_remote_node
                    exec_res = execute_remote_node(node_key, query_clean)
                    st.success(f"Command executed across network! Result: {exec_res}")
                    log_event("SQL_QUERY", f"Remote DML ({node_key})", f"Executed: {query_clean[:80]} | Status: {exec_res.get('status')}", status="SUCCESS", node="SQL Console")
                else:
                    cur.executescript(query_clean)
                    conn.commit()
                    st.success(f"Query executed successfully! Affected rows / DDL statement committed.")
                    log_event("SQL_QUERY", "Mediator DML / DDL", f"Executed statement: {query_clean[:80]}", status="SUCCESS", node="SQL Console")

            conn.close()
        except Exception as e:
            st.error(f"SQL Error: {e}")
            log_event("SQL_QUERY", "SQL Execution Error", f"Target: {selected_target} | Query: {sql_query.strip()[:80]} | Error: {str(e)}", status="ERROR", node="SQL Console")


# =====================================================================
# TAB 4: Manual Data Entry (Add data through GUI)
# =====================================================================
with tab_entry:
    st.title("📝 Manual Database Insertion")
    st.caption("Add new records directly into any of the 4 isolated source databases. Changes immediately reflect in GAV federation.")

    entry_source = st.radio(
        "Choose target database to insert data into:",
        [
            "🏭 Manufacturer (products)",
            "🚚 Distributor (distribution)",
            "🛒 Vendor (sales)",
            "📋 Consumer Affairs (complaints)"
        ],
        horizontal=True
    )

    if entry_source.startswith("🏭"):
        st.subheader("Add New Product to Manufacturer Database")
        with st.form("form_mfr", clear_on_submit=True):
            f_code = st.text_input("Item Code (e.g. MED-1006)*", placeholder="MED-1006")
            f_name = st.text_input("Item Name*", placeholder="Ibuprofen 400mg")
            f_mfr = st.selectbox("Manufacturer Name*", ["Cipla Ltd", "Sun Pharma", "Dr. Reddy's", "Lupin", "Torrent"])
            f_batch = st.text_input("Batch Number", placeholder="B99Z")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                f_mfg = st.date_input("Mfg Date", datetime.date.today())
            with col_m2:
                f_exp = st.date_input("Expiry Date", datetime.date.today() + datetime.timedelta(days=730))
            with col_m3:
                f_mrp = st.number_input("MRP (₹)", min_value=0.0, value=50.0, step=5.0)

            submitted = st.form_submit_button("➕ Insert Product into manufacturer.db", type="primary")
            if submitted:
                if not f_code.strip() or not f_name.strip():
                    st.error("Please provide both Item Code and Item Name.")
                else:
                    try:
                        from federation import execute_remote_node
                        res = execute_remote_node(
                            "manufacturer",
                            "INSERT INTO products (mfr_item_code, item_name, manufacturer_name, batch_no, mfg_date, expiry_date, mrp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            [f_code.strip(), f_name.strip(), f_mfr, f_batch.strip(), str(f_mfg), str(f_exp), f_mrp]
                        )
                        st.success(f"✅ Product `{f_code.strip()}` successfully added to Laptop 1 (Manufacturer)!")
                        log_event("DATA_ENTRY", "Insert Product", f"Added '{f_code.strip()}' ({f_name.strip()}) by {f_mfr}, MRP: ₹{f_mrp}", status="SUCCESS", node="Laptop 1 (Manufacturer)")
                        st.session_state["last_created_qr"] = {
                            "code": f_code.strip(),
                            "name": f_name.strip(),
                            "mfr": f_mfr,
                            "batch": f_batch.strip()
                        }
                    except Exception as e:
                        st.error(f"Failed to insert: {e}")
                        log_event("DATA_ENTRY", "Insert Product Failed", f"Code: {f_code.strip()} | Error: {str(e)}", status="ERROR", node="Laptop 1 (Manufacturer)")

        # Render generated QR code sticker for newly created product
        if "last_created_qr" in st.session_state:
            item_meta = st.session_state["last_created_qr"]
            st.markdown("---")
            st.subheader("🏷️ Official Anti-Counterfeit Packaging QR Sticker")
            qcol1, qcol2 = st.columns([1, 2])
            with qcol1:
                qr_buf = generate_qr_image(item_meta["code"], {"product": item_meta["name"], "manufacturer": item_meta["mfr"]})
                st.image(qr_buf, width=150)
            with qcol2:
                st.write(f"**Item Code:** `{item_meta['code']}`\n- **Product:** {item_meta['name']}\n- **Manufacturer:** {item_meta['mfr']}\n- **Batch:** {item_meta['batch']}")
                st.download_button(
                    "📥 Download Official Packaging QR (PNG)",
                    data=qr_buf.getvalue(),
                    file_name=f"QR_{item_meta['code']}.png",
                    mime="image/png"
                )

    elif entry_source.startswith("🚚"):
        st.subheader("Add Distribution Record to Distributor Database")
        with st.form("form_dist", clear_on_submit=True):
            d_code = st.text_input("Supplier Code (Item Code)*", placeholder="MED-1004")
            d_dist = st.selectbox("Distributor Name*", ["MedLine Distributors", "HealthChain Supply", "Apex Logistics", "PharmaCare"])
            d_vendor = st.selectbox("Target Vendor Name*", ["Apollo Pharmacy", "Wellness Forever", "MedPlus", "Guardian Pharmacy"])
            d_qty = st.number_input("Quantity Dispatched", min_value=1, value=200, step=50)
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                d_date = st.date_input("Dispatch Date", datetime.date.today())
            with col_d2:
                d_region = st.selectbox("Region*", ["Delhi NCR", "Mumbai", "Bengaluru", "Kolkata", "Chennai", "Hyderabad"])

            submitted = st.form_submit_button("➕ Insert Dispatch into distributor.db", type="primary")
            if submitted:
                if not d_code.strip():
                    st.error("Item Code cannot be empty.")
                else:
                    try:
                        from federation import execute_remote_node
                        res = execute_remote_node(
                            "distributor",
                            "INSERT INTO distribution (supplier_code, distributor_name, vendor_name, qty, dispatch_date, region) VALUES (?, ?, ?, ?, ?, ?)",
                            [d_code.strip(), d_dist, d_vendor, d_qty, str(d_date), d_region]
                        )
                        st.success(f"✅ Distribution record for `{d_code.strip()}` added to Laptop 2 (Distributor)!")
                        log_event("DATA_ENTRY", "Insert Distribution", f"Dispatched '{d_code.strip()}' via {d_dist} to {d_vendor} ({d_region}, Qty: {d_qty})", status="SUCCESS", node="Laptop 2 (Distributor)")
                    except Exception as e:
                        st.error(f"Failed to insert: {e}")
                        log_event("DATA_ENTRY", "Insert Distribution Failed", f"Code: {d_code.strip()} | Error: {str(e)}", status="ERROR", node="Laptop 2 (Distributor)")

    elif entry_source.startswith("🛒"):
        st.subheader("Record Point-of-Sale Scan into Vendor Database")
        with st.form("form_sale", clear_on_submit=True):
            s_code = st.text_input("Scanned Code (Item Code)*", placeholder="MED-1002")
            s_desc = st.text_input("Description", placeholder="Prescription dispense")
            s_vendor = st.selectbox("Vendor / Store ID*", ["Apollo Pharmacy", "Wellness Forever", "MedPlus", "Roadside Kiosk"])
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                s_price = st.number_input("Sale Price (₹)*", min_value=0.0, value=65.0, step=5.0)
            with col_s2:
                s_date = st.date_input("Sale Date", datetime.date.today())

            submitted = st.form_submit_button("➕ Record Sale into vendor.db", type="primary")
            if submitted:
                if not s_code.strip():
                    st.error("Scanned Code cannot be empty.")
                else:
                    try:
                        from federation import execute_remote_node
                        res = execute_remote_node(
                            "vendor",
                            "INSERT INTO sales (scanned_code, description, vendor_id, sale_price, sale_date) VALUES (?, ?, ?, ?, ?)",
                            [s_code.strip(), s_desc.strip(), s_vendor, s_price, str(s_date)]
                        )
                        st.success(f"✅ Sale scan for `{s_code.strip()}` recorded to Laptop 3 (Retail)!")
                        log_event("DATA_ENTRY", "Record Point-of-Sale", f"Sold '{s_code.strip()}' at {s_vendor} for ₹{s_price}", status="SUCCESS", node="Laptop 3 (Retail)")
                    except Exception as e:
                        st.error(f"Failed to insert: {e}")
                        log_event("DATA_ENTRY", "Record Sale Failed", f"Code: {s_code.strip()} | Error: {str(e)}", status="ERROR", node="Laptop 3 (Retail)")

    elif entry_source.startswith("📋"):
        st.subheader("File Counterfeit Complaint into Consumer Affairs Database")
        with st.form("form_complaint", clear_on_submit=True):
            c_code = st.text_input("Flagged Code (Item Code)*", placeholder="MED-1001")
            c_reason = st.text_area("Reason for Complaint*", placeholder="Counterfeit packaging, missing tamper seal, or adverse reaction...")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                c_status = st.selectbox("Investigation Status*", ["Verified Nakli", "Under Investigation", "Dismissed"])
            with col_c2:
                c_date = st.date_input("Reported Date", datetime.date.today())

            submitted = st.form_submit_button("➕ File Complaint in consumer_affairs.db", type="primary")
            if submitted:
                if not c_code.strip() or not c_reason.strip():
                    st.error("Flagged Code and Reason are required.")
                else:
                    try:
                        from federation import execute_remote_node
                        res = execute_remote_node(
                            "consumer_affairs",
                            "INSERT INTO complaints (flagged_code, reason, reported_on, status) VALUES (?, ?, ?, ?)",
                            [c_code.strip(), c_reason.strip(), str(c_date), c_status]
                        )
                        st.success(f"✅ Fraud report for `{c_code.strip()}` filed to Laptop 3 (Consumer Affairs)!")
                        log_event("DATA_ENTRY", "File Fraud Complaint", f"Reported '{c_code.strip()}' status: '{c_status}' | Reason: {c_reason.strip()[:60]}", status="WARNING" if c_status == "Verified Nakli" else "INFO", node="Laptop 3 (Consumer Affairs)")
                    except Exception as e:
                        st.error(f"Failed to insert: {e}")
                        log_event("DATA_ENTRY", "File Complaint Failed", f"Code: {c_code.strip()} | Error: {str(e)}", status="ERROR", node="Laptop 3 (Consumer Affairs)")


# =====================================================================
# TAB 5: Analytics Warehouse (View Selection / Maintenance / Adaptation / CUBE)
# =====================================================================
with tab_warehouse:
    st.title("📊 Analytics Warehouse")
    st.caption(
        "Materialized views built ON TOP of the GAV mediator, for questions about the "
        "overall picture rather than one item — e.g. total sales by region, fake-item "
        "counts. This tab demonstrates view selection, incremental maintenance, view "
        "adaptation, and CUBE-style aggregate reporting."
    )

    st.header("1️⃣ View Selection (Greedy Benefit/Cost)")
    st.write(
        "Three candidate analytical views compete for a deliberately tight storage "
        "budget. Query frequencies are stated assumptions (standing in for real "
        "production logs), exactly like the lecture's worked example."
    )
    if st.button("Run greedy view selection", key="btn_view_select"):
        selected, trace = warehouse.greedy_view_selection(verbose=False)
        rows = [
            {
                "Candidate view": t["candidate"],
                "Benefit (cost saved/day)": t["benefit"],
                "Size (bytes)": t["size_bytes"],
                "Efficiency (Benefit/Size)": t["efficiency"],
                "Decision": "✅ Selected" if t["selected"] else "❌ Skipped (over budget)",
            }
            for t in trace
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        st.info(f"Storage budget: {warehouse.STORAGE_BUDGET_BYTES} bytes. Selected: {selected}")
        log_event("WAREHOUSE", "Greedy View Selection", f"Optimized storage: Selected {selected} within {warehouse.STORAGE_BUDGET_BYTES}B budget", status="SUCCESS", node="Warehouse")

    st.divider()
    st.header("Build / Rebuild the Warehouse")
    st.write("Materializes candidate views by pulling once from the live GAV mediator.")
    if st.button("Build warehouse now", type="primary", key="btn_build_wh"):
        warehouse.build_warehouse()
        st.success("warehouse.db built from the GAV mediator.")
        log_event("WAREHOUSE", "Build Materialized Views", "Rebuilt warehouse.db materialized views from live GAV mediator", status="SUCCESS", node="Warehouse")

    wh_path = warehouse.WAREHOUSE_PATH
    if not os.path.exists(wh_path):
        st.warning("Warehouse not built yet — click 'Build warehouse now' above to view materialized views.")
    else:
        conn = sqlite3.connect(wh_path)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**MV_region_summary**")
            st.dataframe(pd.read_sql("SELECT * FROM MV_region_summary", conn), use_container_width=True)
        with c2:
            st.markdown("**MV_manufacturer_summary**")
            st.dataframe(pd.read_sql("SELECT * FROM MV_manufacturer_summary", conn), use_container_width=True)
        with c3:
            st.markdown("**MV_verdict_summary**")
            st.dataframe(pd.read_sql("SELECT * FROM MV_verdict_summary", conn), use_container_width=True)
        conn.close()

    st.divider()
    st.header("2️⃣ View Maintenance (Incremental, not Full Refresh)")
    st.write(
        "SUM is additive, so a new sale only touches the ONE affected row in each "
        "MV — no re-scan. A new complaint that flips an item's verdict is handled "
        "as UPDATE = DELETE-then-INSERT, using an auxiliary state table "
        "(`item_verdict_state`) to know the item's old verdict without rescanning."
    )
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.markdown("**Simulate a new sale**")
        with st.form("new_sale_form"):
            i_code = st.text_input("Item code", "MED-1002")
            price = st.number_input("Sale price", value=66.0)
            region = st.text_input("Region (blank if unknown)", "Delhi NCR")
            manuf = st.text_input("Manufacturer (blank if unknown)", "Sun Pharma")
            submitted = st.form_submit_button("Apply incremental update")
            if submitted:
                if not os.path.exists(warehouse.WAREHOUSE_PATH):
                    st.warning("Build the warehouse first before running maintenance.")
                else:
                    touched = warehouse.maintain_after_new_sale(
                        i_code, price, region=region or None, manufacturer_name=manuf or None
                    )
                    st.success("Applied without a full refresh:")
                    for t in touched:
                        st.write("•", t)
                    log_event("WAREHOUSE", "Incremental View Maintenance", f"Updated MVs for sale '{i_code}' (₹{price}) without full scan: {len(touched)} rows touched", status="SUCCESS", node="Warehouse")

    with mcol2:
        st.markdown("**Simulate a new complaint**")
        with st.form("new_complaint_form"):
            c_code = st.text_input("Item code to flag", "MED-1001")
            reason = st.text_input("Reason", "Tampered hologram seal")
            submitted2 = st.form_submit_button("File complaint + apply delta")
            if submitted2:
                ca_conn = sqlite3.connect(os.path.join(data_dir, "consumer_affairs.db"))
                ca_conn.execute(
                    "INSERT INTO complaints (flagged_code, reason, reported_on, status) VALUES (?,?,?,?)",
                    (c_code, reason, "2026-09-16", "Verified Nakli"),
                )
                ca_conn.commit()
                ca_conn.close()
                if not os.path.exists(warehouse.WAREHOUSE_PATH):
                    st.warning("Complaint inserted into consumer_affairs.db, but build warehouse first to run maintenance.")
                else:
                    touched = warehouse.maintain_after_new_complaint(c_code)
                    st.success("Applied without a full refresh:")
                    for t in touched:
                        st.write("•", t)
                    log_event("WAREHOUSE", "Incremental View Maintenance", f"Updated MVs for complaint '{c_code}' without full scan: {len(touched)} rows touched", status="SUCCESS", node="Warehouse")

    st.divider()
    st.header("3️⃣ View Adaptation")
    st.write(
        "What happens when someone asks for a breakdown the current MV was never "
        "built to answer?"
    )
    acol1, acol2 = st.columns(2)
    with acol1:
        st.markdown("**Case A — NOT adaptable:** ask `MV_region_summary` for a region × manufacturer split")
        if st.button("Try adapting MV_region_summary"):
            if not os.path.exists(warehouse.WAREHOUSE_PATH):
                st.warning("Build warehouse first.")
            else:
                msg, rows = warehouse.adapt_region_summary_to_include_manufacturer()
                st.error(msg) if "NOT" in msg else st.success(msg)
                if rows:
                    st.dataframe(pd.DataFrame(rows, columns=["region", "manufacturer", "sales_val", "count"]), use_container_width=True)
                log_event("WAREHOUSE", "View Adaptation Test", f"Tested adaptation of MV_region_summary: {'Failed' if 'NOT' in msg else 'Success'}", status="INFO", node="Warehouse")
    with acol2:
        st.markdown("**Case B — Adaptable:** roll up `MV_region_manufacturer_fine` to region-only")
        if st.button("Try rolling up the fine-grain view"):
            if not os.path.exists(warehouse.WAREHOUSE_PATH):
                st.warning("Build warehouse first.")
            else:
                msg, rows = warehouse.rollup_region_only_from_fine_grain()
                st.success(msg)
                st.dataframe(pd.DataFrame(rows, columns=["region", "total_sales_value", "item_count"]), use_container_width=True)
                log_event("WAREHOUSE", "View Rollup / Adaptation", f"Rolled up fine-grained view to region-only: {len(rows)} groups", status="SUCCESS", node="Warehouse")

    st.divider()
    st.header("4️⃣ Aggregate Data — hand-rolled CUBE(region, manufacturer)")
    st.write("SQLite has no native `CUBE`/`ROLLUP`, so this is built as the union of all groupings by hand — which is exactly what `CUBE` computes internally.")
    if st.button("Compute CUBE(region, manufacturer)"):
        if not os.path.exists(warehouse.WAREHOUSE_PATH):
            st.warning("Build warehouse first.")
        else:
            rows = warehouse.cube_region_manufacturer()
            df_cube = pd.DataFrame(
                [{"region": r[0], "manufacturer_name": r[1], "total_sales_value": r[2], "item_count": r[3]} for r in rows]
            )
            st.dataframe(df_cube, use_container_width=True)
            log_event("WAREHOUSE", "Compute CUBE", f"Computed CUBE(region, manufacturer): generated {len(rows)} group combinations", status="SUCCESS", node="Warehouse")


# =====================================================================
# TAB 6: Geospatial Counterfeit Risk & Supply Chain Heatmap
# =====================================================================
with tab_heatmap:
    st.title("🗺️ Geospatial Counterfeit Risk & Supply Chain Heatmap")
    st.caption(
        "Real-time geographic risk intelligence synthesizing multi-source data: "
        "authorized distribution dispatches, retail sales scans, and consumer counterfeit complaints "
        "across major pharmaceutical supply hubs in India."
    )

    risk_df = geo_analytics.get_regional_risk_data()

    # High-level KPIs
    total_dispatched_units = int(risk_df["Units Dispatched"].sum())
    total_sales_scans = int(risk_df["Sales Recorded"].sum())
    total_nakli_incidents = int(risk_df["Verified Nakli"].sum())
    under_inv_incidents = int(risk_df["Under Investigation"].sum())

    # Identify top risk region
    sorted_df = risk_df.sort_values(by="Risk Score", ascending=False)
    top_risk_row = sorted_df.iloc[0] if not sorted_df.empty else None

    hm1, hm2, hm3, hm4 = st.columns(4)
    with hm1:
        if top_risk_row is not None and top_risk_row["Risk Score"] > 0:
            st.metric("🚨 Highest Risk Hotspot", f"{top_risk_row['Region']}", f"Risk: {top_risk_row['Risk Score']}/100")
        else:
            st.metric("🚨 Highest Risk Hotspot", "None", "All clean")
    with hm2:
        st.metric("⚠️ Confirmed Nakli Incidents", total_nakli_incidents, delta=f"{under_inv_incidents} under probe", delta_color="inverse")
    with hm3:
        st.metric("📦 Monitored Dispatched Units", f"{total_dispatched_units:,}")
    with hm4:
        clean_rate = round(100.0 * (1.0 - (total_nakli_incidents / max(1, total_sales_scans))), 1)
        st.metric("🛡️ Supply Chain Integrity Rate", f"{clean_rate}%")

    st.divider()

    mcol_map, mcol_info = st.columns([3, 2])

    with mcol_map:
        st.subheader("Interactive Counterfeit Density Heatmap")
        st.caption("🔴 Red: High Counterfeit Risk Hotspot | 🟠 Orange: Suspicious Activity | 🟢 Green: Verified Clean Channel")
        risk_map = geo_analytics.build_risk_map(risk_df)
        st_folium(risk_map, width=720, height=480)

    with mcol_info:
        st.subheader("Regional Risk Breakdown")
        display_cols = ["Region", "Risk Level", "Risk Score", "Verified Nakli", "Units Dispatched", "Sales Recorded"]
        st.dataframe(
            risk_df[display_cols].sort_values(by="Risk Score", ascending=False),
            use_container_width=True,
            height=280
        )

        st.subheader("🚨 Enforcement & Regulatory Guidance")
        if top_risk_row is not None and top_risk_row["Risk Score"] >= 40:
            st.error(
                f"**Immediate Action for {top_risk_row['Region']}:**\n"
                f"- Flagged items detected: `{top_risk_row['Flagged Items']}`\n"
                f"- {top_risk_row['Verified Nakli']} confirmed counterfeit product(s) sold at retail/kiosks.\n"
                f"- **Recommendation**: Dispatch Consumer Affairs drug inspectors to audit local distribution manifests and freeze retail sales."
            )
        else:
            st.success("All monitored regions are currently within acceptable supply chain integrity thresholds.")

        if st.button("🔄 Refresh Geospatial Intelligence", key="btn_refresh_geo", use_container_width=True):
            log_event("SYSTEM", "Geospatial Heatmap Refreshed", "Recalculated regional counterfeit risk metrics", status="INFO", node="Analytics Mediator")
            st.rerun()


# =====================================================================
# TAB 7: Process & System Activity Logs (Audit Trail with Timestamps)
# =====================================================================
with tab_logs:
    st.title("📜 Process & System Activity Logs")
    st.caption(
        "Real-time event log with precise timestamps tracking all operations across the distributed system: "
        "Wi-Fi federated network queries, decision engine provenance evaluations, SQL console runs, "
        "manual data insertions, and data warehouse maintenance cycles."
    )

    all_raw_logs = get_logs(limit=500)
    total_count = len(all_raw_logs)

    # Key Performance / Activity Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Logged Events", total_count)
    with m2:
        fed_cnt = sum(1 for l in all_raw_logs if l.get("category") == "FEDERATION")
        st.metric("📡 Federation Queries", fed_cnt)
    with m3:
        dec_cnt = sum(1 for l in all_raw_logs if l.get("category") == "DECISION_ENGINE")
        st.metric("🧠 Decision Verifications", dec_cnt)
    with m4:
        sql_cnt = sum(1 for l in all_raw_logs if l.get("category") == "SQL_QUERY")
        st.metric("💻 SQL Executions", sql_cnt)
    with m5:
        ent_cnt = sum(1 for l in all_raw_logs if l.get("category") in ("DATA_ENTRY", "WAREHOUSE"))
        st.metric("📝 Data & Warehouse", ent_cnt)

    st.divider()

    # Filtering & Controls
    fcol1, fcol2, fcol3, fcol4 = st.columns([2, 2, 3, 2])
    with fcol1:
        cat_choices = ["ALL", "FEDERATION", "DECISION_ENGINE", "SQL_QUERY", "DATA_ENTRY", "WAREHOUSE", "SYSTEM"]
        sel_cat = st.selectbox("Filter by Category:", cat_choices, index=0)
    with fcol2:
        stat_choices = ["ALL", "SUCCESS", "WARNING", "ERROR", "INFO"]
        sel_stat = st.selectbox("Filter by Status:", stat_choices, index=0)
    with fcol3:
        search_kw = st.text_input("Search Logs (Code, Query, Node, etc.):", placeholder="e.g. MED-1001, Laptop 1, SELECT...")
    with fcol4:
        limit_val = st.number_input("Max entries to show:", min_value=10, max_value=500, value=100, step=25)

    # Filter application
    filtered = all_raw_logs
    if sel_cat != "ALL":
        filtered = [l for l in filtered if l.get("category") == sel_cat]
    if sel_stat != "ALL":
        filtered = [l for l in filtered if l.get("status") == sel_stat]
    if search_kw.strip():
        kw = search_kw.strip().lower()
        filtered = [
            l for l in filtered
            if kw in l.get("action", "").lower()
            or kw in l.get("details", "").lower()
            or kw in l.get("node", "").lower()
            or kw in l.get("timestamp", "").lower()
        ]

    filtered = filtered[:int(limit_val)]

    # Action buttons: Refresh and Clear
    bcol1, bcol2, bcol3, bcol4 = st.columns([2, 2, 2, 4])
    with bcol1:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()
    with bcol2:
        if st.button("🗑️ Clear All Logs", use_container_width=True):
            clear_logs()
            st.success("All logs cleared!")
            st.rerun()
    with bcol3:
        if filtered:
            import io
            df_export = pd.DataFrame(filtered)
            csv_data = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Export CSV",
                data=csv_data,
                file_name=f"asli_nakli_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    st.write(f"Showing **{len(filtered)}** of **{total_count}** logged operations:")

    if filtered:
        # Display as a nicely formatted DataFrame table
        def status_icon(st_val):
            return {
                "SUCCESS": "✅ SUCCESS",
                "WARNING": "⚠️ WARNING",
                "ERROR": "❌ ERROR",
                "INFO": "ℹ️ INFO"
            }.get(st_val, st_val)

        def cat_icon(cat_val):
            return {
                "FEDERATION": "📡 FEDERATION",
                "DECISION_ENGINE": "🧠 DECISION_ENGINE",
                "SQL_QUERY": "💻 SQL_QUERY",
                "DATA_ENTRY": "📝 DATA_ENTRY",
                "WAREHOUSE": "📊 WAREHOUSE",
                "SYSTEM": "⚙️ SYSTEM"
            }.get(cat_val, cat_val)

        table_rows = []
        for l in filtered:
            table_rows.append({
                "Timestamp": l.get("timestamp"),
                "Origin / Node": l.get("node", "Mediator"),
                "Category": cat_icon(l.get("category", "")),
                "Status": status_icon(l.get("status", "")),
                "Action": l.get("action", ""),
                "Process Details": l.get("details", "")
            })

        df_display = pd.DataFrame(table_rows)
        st.dataframe(df_display, use_container_width=True, height=450)

        with st.expander("🔍 Live Raw JSON Inspector"):
            st.json(filtered)
    else:
        st.info("No logs match the selected filter. Perform an item lookup, execute a query, or add a record to generate live activity logs.")

