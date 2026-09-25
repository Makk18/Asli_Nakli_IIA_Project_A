# Schema Mapping: GAV and LAV for the Asli-Nakli Global Schema

This follows the exact notation used in the course's CarRentalAvailability
example ("Write the mappings between Global and Local schemas using both
GAV and LAV"). We implement and run the GAV mapping; the LAV mapping below
is derived for comparison, exactly as the lecture question asks for both.

## Global Schema (chosen by us, as the mediator's global schema)

```
GlobalItem        (item_code, item_name, manufacturer_name, batch_no, mfg_date, expiry_date, mrp)
GlobalDistribution(item_code, distributor_name, vendor_name, qty, dispatch_date, region)
GlobalSale        (item_code, description, vendor_id, sale_price, sale_date)
GlobalComplaint   (item_code, reason, reported_on, status)
```

## Local Schemas (the 4 independent sources)

```
Source Manufacturer:      products     (mfr_item_code, item_name, manufacturer_name, batch_no, mfg_date, expiry_date, mrp)
Source Distributor:       distribution (dist_id, supplier_code, distributor_name, vendor_name, qty, dispatch_date, region)
Source Vendor:             sales        (sale_id, scanned_code, description, vendor_id, sale_price, sale_date)
Source ConsumerAffairs:    complaints   (complaint_id, flagged_code, reason, reported_on, status)
```

---

## GAV Mapping (Global-As-View) — what we actually implement

Per the lecture: *"Global schema defined in terms of sources (global schema
centric or Global-As-View (GAV))... Query reformulation easier."*

Unlike the lecture's CarRentalAvailability example — where Hertz and Budget
both hold *overlapping* car-rental data and so their contributions had to be
`UNION`-ed into one global relation — our four sources are *complementary*:
each covers a different, non-overlapping slice of an item's lifecycle. So
each global relation here maps to exactly **one** source, with no `UNION`
required. This is still GAV (the global schema is still defined purely in
terms of the sources), just the simpler case of it.

```sql
CREATE VIEW GlobalItem AS
SELECT mfr_item_code AS item_code, item_name, manufacturer_name,
       batch_no, mfg_date, expiry_date, mrp
FROM Manufacturer.products;

CREATE VIEW GlobalDistribution AS
SELECT supplier_code AS item_code, distributor_name, vendor_name,
       qty, dispatch_date, region
FROM Distributor.distribution;

CREATE VIEW GlobalSale AS
SELECT scanned_code AS item_code, description, vendor_id,
       sale_price, sale_date
FROM Vendor.sales;

CREATE VIEW GlobalComplaint AS
SELECT flagged_code AS item_code, reason, reported_on, status
FROM ConsumerAffairs.complaints;
```

These four `CREATE VIEW` statements are executed verbatim (as SQLite temp
views over `ATTACH`ed databases) in `federation.py`. Every query the mediator
answers is written against `GlobalItem` / `GlobalDistribution` / `GlobalSale`
/ `GlobalComplaint` only — never against a source's local column names —
which is exactly the lecture's "query reformulation reduces to view
unfolding (polynomial)" property: SQLite substitutes the view definition
back in automatically.

## LAV Mapping (Local-As-View) — derived for comparison, not executed

Per the lecture: *"Sources defined in terms of global schema (source-centric
or Local-As-View (LAV))... query reformulation complex... allows adding a
source independently of others."* Following the lecture's own
`Create Source <Source>.<Table> AS SELECT ... FROM <Global>` notation:

```sql
Create Source Manufacturer.products AS
  Select item_code AS mfr_item_code, item_name, manufacturer_name,
         batch_no, mfg_date, expiry_date, mrp
  From GlobalItem;

Create Source Distributor.distribution AS
  Select item_code AS supplier_code, distributor_name, vendor_name,
         qty, dispatch_date, region
  From GlobalDistribution;

Create Source Vendor.sales AS
  Select item_code AS scanned_code, description, vendor_id,
         sale_price, sale_date
  From GlobalSale;

Create Source ConsumerAffairs.complaints AS
  Select item_code AS flagged_code, reason, reported_on, status
  From GlobalComplaint;
```

## Why GAV was chosen over LAV for this project

The lecture states the selection criteria directly:

| | GAV | LAV |
|---|---|---|
| Best when | "Few, stable, data sources, well-known to the mediator" | "Many, relatively unknown data sources, possibility of addition/deletion" |
| Query reformulation | Easy — view unfolding (polynomial) | Hard — answering queries using views only |
| Modularity | Not modular — adding a source changes the mediated schema | Modular — adding a source is easy |

Our project has exactly **4 fixed, known-in-advance sources** that will not
change during Part A — the textbook case for GAV. LAV's main advantage
(easy addition of new, unknown sources) is not something this project needs
yet, and its cost (hard query reformulation) is not worth paying for. This
also matches the "few, stable, well-known" examples the lecture gives —
Garlic, TSIMMIS, HERMES — which are corporate/enterprise integration systems
much like our closed 4-source setup, rather than InfoMaster/Havasu-style
systems built for many unpredictable web sources.
