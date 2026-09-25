# Asli ya Nakli — 3-Laptop Wi-Fi Federation Setup Guide

This guide explains how to run the project across **three physical laptops** connected to the **same Wi-Fi or mobile hotspot**.

---

## 💻 The 3-Laptop Allocation

Every laptop runs its service on the **standard single port 5000** (no confusing multiple local ports):

| Laptop | Role | Database Hosted | Command to Run |
| :--- | :--- | :--- | :--- |
| **Laptop 1** | Supply-Chain Origin (Manufacturer) | `manufacturer.db` | `python laptop_1_manufacturer.py` |
| **Laptop 2** | Supply-Chain Logistics (Distributor) | `distributor.db` | `python laptop_2_distributor.py` |
| **Laptop 3** | Retail, Consumer Affairs & Central Mediator GUI | `vendor.db` & `consumer_affairs.db` | `python laptop_3_retail_and_consumer.py`<br>`streamlit run app.py` |

---

## 🚀 Step-by-Step Execution

### Step 1: Connect all 3 laptops to the SAME Wi-Fi or Mobile Hotspot
Make sure Laptop 1, Laptop 2, and Laptop 3 are connected to the same Wi-Fi router or phone hotspot.

---

### Step 2: Start the Service on Laptop 1 (Manufacturer)
On **Laptop 1**, open terminal:
```powershell
python laptop_1_manufacturer.py
```
When it starts, it will automatically print its local Wi-Fi IP address:
```text
================================================================
  [LAPTOP 1] MANUFACTURER DATABASE NODE
  Local Wi-Fi IP : 192.168.1.10
  Port           : 5000
  Enter on Laptop 3 GUI: http://192.168.1.10:5000
================================================================
```
*(Note down Laptop 1's IP address, e.g. `192.168.1.10`)*

---

### Step 3: Start the Service on Laptop 2 (Distributor)
On **Laptop 2**, open terminal:
```powershell
python laptop_2_distributor.py
```
It will also print its local Wi-Fi IP address:
```text
================================================================
  [LAPTOP 2] DISTRIBUTOR DATABASE NODE
  Local Wi-Fi IP : 192.168.1.15
  Port           : 5000
  Enter on Laptop 3 GUI: http://192.168.1.15:5000
================================================================
```
*(Note down Laptop 2's IP address, e.g. `192.168.1.15`)*

---

### Step 4: Start Retail Node & GUI on Laptop 3 (Central Coordinator)
On **Laptop 3**, open two terminal tabs:

**Terminal Tab A (Retail Node):**
```powershell
python laptop_3_retail_and_consumer.py
```

**Terminal Tab B (Central Mediator GUI):**
```powershell
streamlit run app.py
```
Open the browser at `http://localhost:8501`.

---

### Step 5: Configure the IPs in the GUI (10 Seconds)
1. In the Streamlit GUI, look at the **left sidebar**.
2. Click **"⚙️ Configure Laptop IPs (Wi-Fi / LAN)"**.
3. Type in:
   - **Laptop 1 IP**: e.g., `192.168.1.10`
   - **Laptop 2 IP**: e.g., `192.168.1.15`
   - **Laptop 3 IP**: `127.0.0.1` (or Laptop 3's Wi-Fi IP)
4. Click **"💾 Save Laptop IPs"**.

All node indicators will instantly turn **🟢 Online** with live network ping latencies!

---

## 🎤 What to Demo to the Professor

1. **Physical Distribution**: Show the professor the 3 separate physical laptops on your desk.
2. **Real Network Queries**: 
   - Search for `MED-1001` in Tab 1 of the GUI.
   - Show the green badges: `📡 Laptop 1 Network Node : http://192.168.1.10:5000`.
   - Turn Laptop 1 around and show the terminal log printing the live incoming HTTP query from Laptop 3!
3. **Fault Tolerance**:
   - Turn off Wi-Fi on Laptop 1 (or press `Ctrl+C`).
   - Refresh GUI: Laptop 1 turns 🔴 Offline.
   - The mediator shows graceful fallback to local cache, proving high availability!
