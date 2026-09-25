"""
geo_analytics.py
----------------
Geospatial Counterfeit Risk Analytics & Heatmap Visualization for Asli ya Nakli.
Integrates live cross-source data from:
  - GlobalDistribution (regions, shipment volume, target vendors)
  - GlobalSale (retail point-of-sale scans & vendor locations)
  - GlobalComplaint (counterfeit reports, investigation statuses)
"""

import sqlite3
import pandas as pd
import folium
from folium.plugins import HeatMap
from federation import get_federated_connection

# Master coordinates for Indian supply chain hubs & retail markets
CITY_COORDINATES = {
    "Delhi NCR": {"lat": 28.6139, "lon": 77.2090, "state": "Delhi / Haryana / UP"},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777, "state": "Maharashtra"},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946, "state": "Karnataka"},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867, "state": "Telangana"},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639, "state": "West Bengal"},
    "Chennai": {"lat": 13.0827, "lon": 80.2707, "state": "Tamil Nadu"},
    "Ahmedabad": {"lat": 23.0225, "lon": 72.5714, "state": "Gujarat"},
    "Pune": {"lat": 18.5204, "lon": 73.8567, "state": "Maharashtra"}
}

# Vendor to default city mapping (for sales scans that bypassed authorized dispatches)
VENDOR_CITY_MAPPING = {
    "Apollo Pharmacy": "Delhi NCR",
    "Wellness Forever": "Mumbai",
    "MedPlus": "Bengaluru",
    "Guardian Pharmacy": "Hyderabad",
    "Roadside Kiosk": "Delhi NCR"
}

def get_regional_risk_data():
    """
    Interrogates the GAV federated mediator to compute regional counterfeit metrics.
    Returns: DataFrame with region, lat, lon, shipments, sales, complaints, nakli_count, risk_score, risk_level.
    """
    conn = get_federated_connection()

    # 1. Distribution by region
    dist_df = pd.read_sql("""
        SELECT region, COUNT(*) AS dispatch_count, SUM(qty) AS total_units
        FROM GlobalDistribution
        GROUP BY region
    """, conn)

    # 2. Sales with region inference
    sales_df = pd.read_sql("""
        SELECT s.item_code, s.vendor_id, s.sale_price, s.sale_date,
               COALESCE(d.region, 'Unknown') AS dist_region
        FROM GlobalSale s
        LEFT JOIN GlobalDistribution d ON s.item_code = d.item_code
    """, conn)

    # 3. Complaints with region inference
    complaints_df = pd.read_sql("""
        SELECT c.item_code, c.reason, c.status,
               COALESCE(d.region, 'Unknown') AS dist_region,
               s.vendor_id
        FROM GlobalComplaint c
        LEFT JOIN GlobalDistribution d ON c.item_code = d.item_code
        LEFT JOIN GlobalSale s ON c.item_code = s.item_code
    """, conn)

    conn.close()

    # Aggregate by City / Region
    regional_stats = {}
    for city, coords in CITY_COORDINATES.items():
        regional_stats[city] = {
            "region": city,
            "state": coords["state"],
            "lat": coords["lat"],
            "lon": coords["lon"],
            "dispatches": 0,
            "units_dispatched": 0,
            "sales_scans": 0,
            "complaints_count": 0,
            "verified_nakli": 0,
            "under_investigation": 0,
            "flagged_items": set()
        }

    # Populate Dispatches
    for _, row in dist_df.iterrows():
        reg = row["region"]
        if reg in regional_stats:
            regional_stats[reg]["dispatches"] += int(row["dispatch_count"])
            regional_stats[reg]["units_dispatched"] += int(row["total_units"] or 0)

    # Populate Sales
    for _, row in sales_df.iterrows():
        reg = row["dist_region"]
        if reg == "Unknown":
            reg = VENDOR_CITY_MAPPING.get(row["vendor_id"], "Delhi NCR")
        if reg in regional_stats:
            regional_stats[reg]["sales_scans"] += 1

    # Populate Complaints & Counterfeit reports
    for _, row in complaints_df.iterrows():
        reg = row["dist_region"]
        if reg == "Unknown":
            reg = VENDOR_CITY_MAPPING.get(row["vendor_id"], "Delhi NCR")
        if reg in regional_stats:
            regional_stats[reg]["complaints_count"] += 1
            regional_stats[reg]["flagged_items"].add(row["item_code"])
            if row["status"] == "Verified Nakli":
                regional_stats[reg]["verified_nakli"] += 1
            elif row["status"] == "Under Investigation":
                regional_stats[reg]["under_investigation"] += 1

    # Calculate Risk Score (0 - 100%)
    # Formula: (Verified Nakli * 40) + (Under Investigation * 20) + (Unregulated sales ratio * 15)
    records = []
    for city, s in regional_stats.items():
        score = (s["verified_nakli"] * 45) + (s["under_investigation"] * 25)
        # Cap score between 5 and 100
        score = min(100, max(5 if (s["dispatches"] > 0 or s["sales_scans"] > 0) else 0, score))

        if score >= 60:
            level = "CRITICAL (High Nakli Risk)"
            color = "red"
        elif score >= 25:
            level = "MODERATE (Suspicious Activity)"
            color = "orange"
        elif score > 0:
            level = "LOW (Authentic Supply Chain)"
            color = "green"
        else:
            level = "INACTIVE (No Local Activity)"
            color = "gray"

        records.append({
            "Region": city,
            "State": s["state"],
            "Latitude": s["lat"],
            "Longitude": s["lon"],
            "Dispatches": s["dispatches"],
            "Units Dispatched": s["units_dispatched"],
            "Sales Recorded": s["sales_scans"],
            "Total Complaints": s["complaints_count"],
            "Verified Nakli": s["verified_nakli"],
            "Under Investigation": s["under_investigation"],
            "Flagged Items": ", ".join(s["flagged_items"]) if s["flagged_items"] else "None",
            "Risk Score": score,
            "Risk Level": level,
            "Color": color
        })

    return pd.DataFrame(records)


def build_risk_map(risk_df: pd.DataFrame) -> folium.Map:
    """
    Renders an interactive Leaflet map with HeatMap density and styled CircleMarkers.
    """
    # Center map on India
    m = folium.Map(
        location=[22.8, 79.5],
        zoom_start=5,
        tiles="OpenStreetMap"
    )

    # 1. HeatMap layer
    heat_data = []
    for _, r in risk_df.iterrows():
        if r["Risk Score"] > 0:
            # Normalize weight for heatmap
            weight = max(0.1, r["Risk Score"] / 100.0)
            heat_data.append([r["Latitude"], r["Longitude"], weight])

    if heat_data:
        HeatMap(
            heat_data,
            radius=35,
            blur=25,
            max_zoom=6,
            gradient={0.2: "blue", 0.4: "lime", 0.7: "orange", 1.0: "red"}
        ).add_to(m)

    # 2. Circle Markers for each supply chain node
    for _, r in risk_df.iterrows():
        color = r["Color"]
        radius = 8 + (r["Risk Score"] * 0.15) if r["Risk Score"] > 0 else 6

        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
            <h4 style="margin: 0 0 5px 0; color: {'#d32f2f' if color == 'red' else '#f57c00' if color == 'orange' else '#388e3c'};">
                📍 {r['Region']}
            </h4>
            <div style="font-size: 11px; color: #666; margin-bottom: 8px;">{r['State']}</div>
            <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
                <tr><td><b>Risk Level:</b></td><td><span style="color:{color}; font-weight:bold;">{r['Risk Level']}</span></td></tr>
                <tr><td><b>Risk Score:</b></td><td><b>{r['Risk Score']}/100</b></td></tr>
                <tr><td><b>Dispatched Units:</b></td><td>{r['Units Dispatched']}</td></tr>
                <tr><td><b>Sales Scanned:</b></td><td>{r['Sales Recorded']}</td></tr>
                <tr><td><b>Verified Nakli:</b></td><td><b style="color:red;">{r['Verified Nakli']}</b></td></tr>
                <tr><td><b>In Investigation:</b></td><td>{r['Under Investigation']}</td></tr>
                <tr><td><b>Flagged Codes:</b></td><td><code>{r['Flagged Items']}</code></td></tr>
            </table>
            <div style="margin-top: 8px; font-size: 11px; font-style: italic; color: #444;">
                {'🚨 Immediate raid & inspection recommended' if color == 'red' else '⚠️ Audit vendor distribution receipts' if color == 'orange' else '✅ Verified clean supply chain'}
            </div>
        </div>
        """

        folium.CircleMarker(
            location=[r["Latitude"], r["Longitude"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            weight=2,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{r['Region']}: {r['Risk Level']} (Score: {r['Risk Score']})"
        ).add_to(m)

    return m
