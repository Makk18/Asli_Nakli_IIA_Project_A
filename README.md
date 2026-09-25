# Asli ya Nakli — Traditional Data Integration (Project 2, Part A)

## 1. Scope of work
Given the unique code on an item (as scanned/read at the point of purchase),
produce its complete trust history — manufacturer registration, distribution
trail, vendor sale record, and any consumer-affairs fraud reports — pulled
live from four independently-designed databases, and return a genuine /
suspicious / fake verdict.

## 2. What's innovative
The verdict is **not a single lookup** — it's a decision rule reasoned over
evidence integrated from all four sources at once (e.g. "registered with
manufacturer but never dispatched by any distributor" → *suspicious*, even
though no single source says that on its own). This matches the course's
"decision-centric integration" framing directly.
## Multi-laptop deployment over Wi-Fi
The four source databases run as independent HTTP services on three
laptops connected to the same Wi-Fi network; the Streamlit mediator on
Laptop 3 queries them live, with per-node health checks and latency
monitoring. Setup steps: [SETUP_3_LAPTOPS.md](SETUP_3_LAPTOPS.md)
(sample_activity_logs.json contains logs from a live 3-laptop demo run, showing remote queries and verdicts)

## 3–4. Schema design + populated data
Four separate SQLite files under `data/`, each simulating a system built in
isolation — same real-world attribute (item code), four different column
names:

| Source | File | Table | Item-code column |
|---|---|---|---|
| Manufacturer | `manufacturer.db` | `products` | `mfr_item_code` |
| Distributor | `distributor.db` | `distribution` | `supplier_code` |
| Vendor (POS) | `vendor.db` | `sales` | `scanned_code` |
| Consumer Affairs | `consumer_affairs.db` | `complaints` | `flagged_code` |

Populated with 5 legitimate item chains plus 2 planted fraud cases
(`MED-1004` = diverted stock, `MED-9999` = code that doesn't exist at all).

## 5. Schema matching / mapping — GAV (Global-As-View)
`federation.py` implements the course's **GAV** formalism explicitly: a
Global Schema (`GlobalItem`, `GlobalDistribution`, `GlobalSale`,
`GlobalComplaint`) is defined purely as `CREATE VIEW ... AS SELECT ...`
over the four sources, each renaming its differently-named local column
(`mfr_item_code` / `supplier_code` / `scanned_code` / `flagged_code`) to one
shared `item_code`. No source table is modified. GAV was chosen over LAV
because we have few, fixed, well-known sources — per the lecture, exactly
the case GAV is meant for (LAV is for many, unpredictable sources). The full
GAV mapping, plus the equivalent LAV mapping written out for comparison, is
in `gav_lav_mapping.md`.

## 6. SQL federation
A single SQLite connection uses `ATTACH DATABASE` to open all four files at
once, so **one SQL session can query across all four sources** without
copying anything into a warehouse. Every query is written against the
*global* views only; under GAV this reformulation is "just view unfolding"
— SQLite substitutes each view's definition back in and runs the resulting
per-source SQL automatically. This is genuine (lightweight) federation:
sources stay where they are, queries are decomposed and joined live.

## 7. Communication between data sources
The `ATTACH`ed connection *is* the communication channel between the four
otherwise-unconnected systems — say this explicitly in the demo, since it's
the crux of the "traditional data integration" ask. (In a production system
this role is played by something like Trino/Presto or a Postgres FDW talking
to wrappers around each real source; here SQLite's `ATTACH` plays that role
directly, which is a legitimate simplification for a course project.)

## 8. GUI + query integration demo
`app.py` is a comprehensive Streamlit dashboard:
- **Tab 1: Item Lookup** (GAV-federated mediator)
- **Tab 2: Decision Engine** (Step-by-step provenance decision tree & live execution trace)
- **Tab 3: SQL Query Console** (Run arbitrary SQL across any database or mediator with results shown in GUI)
- **Tab 4: Manual Data Entry** (Insert data directly into any database through GUI forms)
- **Tab 5: Analytics Warehouse** (DWH extension: view selection, incremental maintenance, adaptation, CUBE)
- **Sidebar Cluster Monitor**: Real-time health status, ports, and latency of distributed instances.

---

## 9. Distributed Multi-Instance Architecture (Concurrent Terminals)

The four databases can run as **independent micro-database network services in concurrent terminals**:

| Terminal | Script | Database | Port | Role |
| :--- | :--- | :--- | :--- | :--- |
| **Terminal 1** | `run_terminal_1_manufacturer.py` | `manufacturer.db` | `:5001` | Product catalog ground truth |
| **Terminal 2** | `run_terminal_2_distributor.py` | `distributor.db` | `:5002` | Wholesale supply-chain dispatches |
| **Terminal 3** | `run_terminal_3_retail.py` | `vendor.db` & `consumer_affairs.db` | `:5003`, `:5004` | Retail point-of-sale scans & fraud complaints |

The mediator coordinates across all 3 terminals over TCP/HTTP network communication. If any terminal is stopped, the mediator gracefully falls back to local storage access.

---

## How to run

### Option A: Concurrent Terminals Mode (Recommended for Demo)

1. Open 3 concurrent terminals:
   ```bash
   # Terminal 1:
   python run_terminal_1_manufacturer.py

   # Terminal 2:
   python run_terminal_2_distributor.py

   # Terminal 3:
   python run_terminal_3_retail.py
   ```
   *(Or double-click `launch_terminals.bat` / run `python launch_terminals.py` to spawn them all automatically!)*

2. In a 4th terminal, launch the centralized GUI:
   ```bash
   streamlit run app.py
   ```

### Option B: Standalone Mode
```bash
python setup_sources.py     # builds the 4 databases + sample data
streamlit run app.py        # opens the GUI directly (uses local fallback)
```

Try these codes in the demo:
- `MED-1001` → ASLI (clean chain: manufacturer → distributor → vendor)
- `MED-1004` → SUSPICIOUS (manufacturer record exists, but no distributor ever shipped it)
- `MED-9999` → NAKLI (no manufacturer record at all — the clearest fake signal)
