"""
launch_terminals.py
--------------------
Spawns the 3 concurrent database instances either as separate terminal windows
(on Windows/Linux/Mac) or as managed subprocesses.

Usage:
  python launch_terminals.py
"""

import subprocess
import sys
import os
import time

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scripts = [
        ("Terminal 1 (Manufacturer: 5001)", "run_terminal_1_manufacturer.py"),
        ("Terminal 2 (Distributor: 5002)", "run_terminal_2_distributor.py"),
        ("Terminal 3 (Retail: 5003 & 5004)", "run_terminal_3_retail.py"),
    ]

    print("================================================================")
    print("[*] Spawning 3 Concurrent Database Instance Terminals...")
    print("================================================================")

    processes = []
    for title, script in scripts:
        script_path = os.path.join(base_dir, script)
        if sys.platform == "win32":
            # Windows: start new terminal window using 'start'
            cmd = f'start "{title}" cmd /k "{sys.executable}" "{script_path}"'
            subprocess.Popen(cmd, shell=True)
            print(f"[+] Launched {title}")
        else:
            # Unix/Mac: launch background process
            p = subprocess.Popen([sys.executable, script_path])
            processes.append(p)
            print(f"[+] Spawned process {title} (PID: {p.pid})")

    print("\nAll database instances have been initialized.")
    print("Next step: Run the centralized GUI in another terminal:")
    print("   streamlit run app.py")

if __name__ == "__main__":
    main()
