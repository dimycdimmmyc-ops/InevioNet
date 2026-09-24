# InevioNet - Deployment Guide

## Quick Start

### Step 1: Install Python on second PC
Download from https://www.python.org/downloads/
IMPORTANT: Check 'Add Python to PATH'

### Step 2: Copy project
Copy E:\InevioNet to second PC (without venv folder)

### Step 3: Install
Double-click: deploy\install_remote.bat

### Step 4: Run
Double-click: deploy\start_remote.bat
Open: https://localhost:8080

## P2P Connection

1. Both PCs must be on same WiFi/LAN
2. Wait 30 sec after both start
3. They will auto-discover each other

### Test from first PC
cd deploy
powershell -ExecutionPolicy Bypass -File check_connection.ps1 -RemoteHost 192.168.1.100

## Troubleshooting

Port 8080 busy:
- Edit web/app.py, change port=8080 to 8081

Firewall:
- Settings > Firewall > Allow app > python.exe

No connection:
- Test-NetConnection <ip> -Port 8080
- Check both PCs on same network

## Optional: Tor / I2P

Tor:
- Download Tor Expert Bundle via VPN
- Extract tor.exe to tor\ folder

I2P:
- Install from https://geti2p.net/
- Enable SAM: http://127.0.0.1:7657/configclients

## Sync between PCs

deploy\sync.bat

## Architecture

PC1 (192.168.1.180)     PC2 (192.168.1.100)
     :8080                    :8080
       |                        |
       +--- Multicast 9555 -----+
       +--- WebRTC P2P ---------+
       +--- I2P ---------------+

All messages encrypted + signed.
