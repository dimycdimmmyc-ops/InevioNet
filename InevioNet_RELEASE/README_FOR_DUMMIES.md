# InevioNet - Quick Start

## What is it?

Decentralized P2P network with self-evolution.
Works like mycelium - finds networks, infiltrates, grows.

## Install (once)

1. Download Python 3.11+: https://www.python.org/downloads/
   IMPORTANT: check 'Add Python to PATH'
2. Double-click install.bat
3. Wait 5-10 min

## Run (every time)

1. Double-click start.bat
2. Open browser: https://localhost:8080
3. Accept certificate

## UI sections

- Network map - nodes, WiFi, spores
- Industrial - Modbus/MQTT/OPCUA/DNP3 scan
- Stego - hidden transmission
- Evolution - catastrophes + best strategies
- Network Scanners - Tor, BLE, LTE

## Tor test

1. Click 'Check Tor'
2. If AVAILABLE - works

## Troubleshooting

Tor not working:
- Check tor\tor.exe exists
- Run start_tor.bat manually
- Test-NetConnection 127.0.0.1 -Port 9050

BLE not finding:
- Install Visual C++ Build Tools (patch8c.ps1 as admin)

Server not starting:
- python --version
- venv\Scripts\activate
- pip list

## Philosophy

Networks see choice, but there is no choice.
The packet is always delivered.
