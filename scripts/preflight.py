#!/usr/bin/env python3
"""Quick preflight: check if OBS WebSocket server is reachable."""
import socket
import sys

port = int(sys.argv[1]) if len(sys.argv) > 1 else 4444
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(('127.0.0.1', port))
sock.close()

if result == 0:
    print(f"✓ OBS WebSocket server is running on port {port}")
    sys.exit(0)
else:
    print(f"✗ OBS WebSocket server NOT reachable on port {port}")
    print("  → Open OBS → Settings → Advanced → WebSocket Server Settings")
    print("  → Enable 'WebSocket Server' and click OK")
    sys.exit(1)
