#!/usr/bin/env python3
"""
tests/test_obsctl.py — Basic smoke tests for obsctl.py

Run: python3 tests/test_obsctl.py
Requires OBS WebSocket server to be enabled and running.
"""

import subprocess
import sys
import json
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "obsctl.py"
PASSED = 0
FAILED = 0


def run(args, expect_rc=0):
    global PASSED, FAILED
    cmd = [sys.executable, str(SCRIPT)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    ok = result.returncode == expect_rc
    status = "✓" if ok else "✗"
    if ok:
        PASSED += 1
    else:
        FAILED += 1
    label = " ".join(args)
    print(f"  {status} {label}")
    if not ok:
        print(f"     exit={result.returncode}")
        if result.stdout:
            print(f"     stdout: {result.stdout.strip()[:200]}")
        if result.stderr:
            print(f"     stderr: {result.stderr.strip()[:200]}")
    return ok


def main():
    print("obsctl smoke tests\n")

    # 0. Preflight
    print("[0] Preflight")
    preflight = Path(__file__).parent.parent / "scripts" / "preflight.py"
    result = subprocess.run(
        [sys.executable, str(preflight)],
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        print(f"  ✗ Cannot connect to OBS — tests skipped")
        print(f"     {result.stdout.strip()}")
        print("\nEnable OBS WebSocket: Settings → Advanced → WebSocket Server Settings")
        sys.exit(1)
    print("  ✓ Connected to OBS")

    # 1. Read-only commands (safe to run always)
    print("\n[1] Read-only commands")
    run(["system", "version"])
    run(["system", "stats"])
    run(["system", "vidsettings"])
    run(["system", "inputs"])
    run(["scenes", "list"])
    run(["transitions", "list"])
    run(["recording", "status"])
    run(["streaming", "status"])

    # 2. Inputs
    print("\n[2] Inputs")
    run(["inputs", "list"])

    # 3. Scenes — create, switch back, delete
    print("\n[3] Scene lifecycle")
    run(["scenes", "create", "--scene", "__test_scene"])
    run(["scenes", "switch", "--scene", "__test_scene"])
    # Switch back to whatever was current
    run(["scenes", "delete", "--scene", "__test_scene"])

    # 4. Transitions
    print("\n[4] Transitions")
    run(["transitions", "duration", "--duration", "300"])

    # Summary
    print(f"\n{'='*40}")
    print(f"Passed: {PASSED}  Failed: {FAILED}")
    if FAILED:
        sys.exit(1)
    print("All tests passed ✓")


if __name__ == "__main__":
    main()
