@echo off
TITLE Asli ya Nakli - Distributed Multi-Terminal Launcher
echo ================================================================
echo Launching 3 Concurrent Database Instance Terminals...
echo ================================================================

start "TERMINAL 1: Manufacturer DB (:5001)" cmd /k "python run_terminal_1_manufacturer.py"
start "TERMINAL 2: Distributor DB (:5002)" cmd /k "python run_terminal_2_distributor.py"
start "TERMINAL 3: Retail & Consumer Node (:5003, :5004)" cmd /k "python run_terminal_3_retail.py"

echo.
echo All 3 terminals launched successfully!
echo To view the centralized GUI, open a new terminal and run:
echo    streamlit run app.py
echo ================================================================
pause
