#!/usr/bin/env python3
"""
obsctl.py — OBS Studio WebSocket controller for Hermes Agent.
Uses websocket-client directly. Protocol: OBS WebSocket v5.4+ (OBS 28+).

Usage:
    python3 obsctl.py <category> <action> [--flags]
"""

import argparse
import base64
import json
import math
import os
import sys
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────

def _load_env():
    """Load .env from skill directory."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().strip().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

OBS_HOST = os.environ.get("OBS_WS_HOST", "127.0.0.1")
OBS_PORT = int(os.environ.get("OBS_WS_PORT", "4444"))
OBS_PASS = os.environ.get("OBS_WS_PASSWORD", "")


# ── OBS WebSocket Client ────────────────────────────────────────────────────

class ObsError(Exception):
    """Raised when OBS returns an error."""


class ObsClient:
    """Minimal OBS WebSocket client using websocket-client."""

    def __init__(self, host, port, password=None):
        self.host = host
        self.port = port
        self.password = password
        self.ws = None
        self.seq = 0
        self.connected = False

    def connect(self):
        """Connect and authenticate with OBS WebSocket server."""
        import websocket
        self.ws = websocket.WebSocket()
        try:
            self.ws.connect(f"ws://{self.host}:{self.port}")
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to OBS at {self.host}:{self.port}. "
                f"Is the WebSocket Server enabled? (Settings → Advanced)\n"
                f"Details: {e}"
            )

        # Handshake — expect op:0 (success) or op:1 (auth required)
        msg = self._recv()
        if msg.get("op") == 0:
            # No auth needed
            pass
        elif msg.get("op") == 1:
            # Auth required
            pwd = self.password if self.password else ""
            self._send({"op": 2, "d": {"Password": pwd}})
            auth = self._recv()
            if auth.get("op") != 3:
                raise ConnectionError(f"Authentication failed: {auth}")
        else:
            raise ConnectionError(f"Unexpected handshake: {msg}")

        self.connected = True

    def _next_seq(self):
        self.seq += 1
        return self.seq

    def _send(self, msg):
        self.ws.send(json.dumps(msg))

    def _recv(self, timeout=10):
        self.ws.settimeout(timeout)
        raw = self.ws.recv()
        return json.loads(raw)

    def request(self, method, params=None):
        """Send a request, wait for matching response, return params dict."""
        seq = self._next_seq()
        req_id = f"hermes-{seq}"
        payload = {
            "op": 11,
            "d": {
                "requestType": method,
                "requestId": req_id,
            }
        }
        if params:
            payload["d"]["requestParams"] = params
        self._send(payload)

        deadline = time.time() + 10
        while time.time() < deadline:
            msg = self._recv()
            d = msg.get("d", {})
            if msg.get("op") == 11 and d.get("requestId") == req_id:
                if d.get("error"):
                    raise ObsError(f"{method}: {d['error']}")
                return d.get("requestParams", {})
        raise TimeoutError(f"Request {method} timed out")

    def close(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.close()


def _connect():
    """Context manager shortcut."""
    return ObsClient(OBS_HOST, OBS_PORT, OBS_PASS or None)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _bool(val):
    """Parse boolean from string."""
    if val is None:
        return False
    return str(val).lower() in ("true", "1", "yes", "on")


def _fmt_dur(seconds):
    """Format seconds to m:s."""
    if not seconds:
        return "0s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s}s"


# ── Command Handlers ────────────────────────────────────────────────────────

def cmd_scenes(args):
    with _connect() as c:
        if args.action == "list":
            resp = c.request("GetSceneList")
            scenes = resp.get("sceneList", [])
            current = resp.get("currentSceneName", "?")
            print(f"Current: {current}\n")
            for s in scenes:
                name = s if isinstance(s, str) else s.get("sceneName", "?")
                marker = " ◀" if name == current else ""
                print(f"  - {name}{marker}")

        elif args.action == "switch":
            if not args.scene:
                print("ERROR: --scene required", file=sys.stderr)
                return
            c.request("SetCurrentScene", {"sceneName": args.scene})
            print(f"Switched to: {args.scene}")

        elif args.action == "create":
            if not args.scene:
                print("ERROR: --scene required", file=sys.stderr)
                return
            c.request("CreateScene", {"sceneName": args.scene})
            print(f"Created: {args.scene}")

        elif args.action == "delete":
            if not args.scene:
                print("ERROR: --scene required", file=sys.stderr)
                return
            c.request("RemoveScene", {"sceneName": args.scene})
            print(f"Deleted: {args.scene}")


def cmd_sources(args):
    with _connect() as c:
        if args.action == "list":
            if not args.scene:
                print("ERROR: --scene required", file=sys.stderr)
                return
            resp = c.request("GetSceneSceneItems", {"sceneName": args.scene})
            items = resp.get("sceneItems", [])
            print(f"Sources in '{args.scene}' ({len(items)}):")
            for it in items:
                name = it.get("sceneItemName", "?")
                vis = "✓" if it.get("sceneItemVisible", True) else "✗"
                print(f"  [{vis}] {name}")

        elif args.action == "visible":
            if not args.scene or not args.source:
                print("ERROR: --scene and --source required", file=sys.stderr)
                return
            resp = c.request("GetSceneSceneItems", {"sceneName": args.scene})
            target = None
            for it in resp.get("sceneItems", []):
                if it.get("sceneItemName") == args.source:
                    target = it["sceneItemId"]
                    break
            if target is None:
                print(f"ERROR: Source '{args.source}' not found in scene '{args.scene}'")
                return
            c.request("SetSceneItemVisible", {
                "sceneName": args.scene,
                "sceneItemId": target,
                "sceneItemVisible": args.visible,
            })
            print(f"'{args.source}' visible: {args.visible}")

        elif args.action == "volume":
            if not args.source or args.volume is None:
                print("ERROR: --source and --volume required", file=sys.stderr)
                return
            vol = float(args.volume)
            c.request("SetInputVolumeMultiplier", {
                "inputName": args.source,
                "inputVolumeMultiplier": vol,
            })
            gain = 20.0 * math.log10(vol) if vol > 0 else -100.0
            print(f"'{args.source}' volume: {vol:.2f} ({gain:.1f}dB)")

        elif args.action == "mute":
            if not args.source:
                print("ERROR: --source required", file=sys.stderr)
                return
            c.request("SetInputMute", {
                "inputName": args.source,
                "inputMuteState": args.mute,
            })
            print(f"'{args.source}' muted: {args.mute}")


def cmd_recording(args):
    with _connect() as c:
        if args.action == "start":
            c.request("StartRecording")
            print("Recording started")
        elif args.action == "stop":
            c.request("StopRecording")
            print("Recording stopped")
        elif args.action == "pause":
            c.request("PauseRecording")
            print("Recording paused")
        elif args.action == "resume":
            c.request("UnpauseRecording")
            print("Recording resumed")
        elif args.action == "status":
            resp = c.request("GetRecordingStatus")
            running = resp.get("outputDurationSeconds", 0) > 0
            paused = resp.get("isRecordingPaused", False)
            if running and paused:
                status = "PAUSED"
            elif running:
                status = "RECORDING"
            else:
                status = "STOPPED"
            print(f"Recording: {status}")
            dur = resp.get("outputDurationSeconds", 0)
            if dur:
                print(f"Duration: {_fmt_dur(dur)}")


def cmd_streaming(args):
    with _connect() as c:
        if args.action == "start":
            c.request("StartStreaming")
            print("Streaming started")
        elif args.action == "stop":
            c.request("StopStreaming")
            print("Streaming stopped")
        elif args.action == "status":
            resp = c.request("GetStreamingStatus")
            dur = resp.get("outputDurationSeconds", 0)
            print(f"Streaming: {'LIVE' if dur > 0 else 'OFF'}")
            if dur:
                print(f"Duration: {_fmt_dur(dur)}")


def cmd_replay(args):
    with _connect() as c:
        if args.action == "start":
            c.request("StartReplayBuffer")
            print("Replay buffer started")
        elif args.action == "stop":
            c.request("StopReplayBuffer")
            print("Replay buffer stopped")
        elif args.action == "save":
            c.request("SaveReplayBuffer")
            print("Replay saved!")


def cmd_system(args):
    with _connect() as c:
        if args.action == "version":
            resp = c.request("GetVersion")
            print(f"OBS: {resp.get('obsVersion', '?')}")
            print(f"Protocol: {resp.get('rpcVersion', '?')}")

        elif args.action == "stats":
            resp = c.request("GetStats")
            print(f"FPS: {resp.get('activeFps', '?')}")
            print(f"CPU: {resp.get('cpuUsage', '?')}%")
            print(f"Rendered frames: {resp.get('renderedFrameCount', '?')}")
            print(f"Dropped frames: {resp.get('droppedFrameCount', '?')}")
            print(f"Consecutive drops: {resp.get('consecutivelyDroppedFrameCount', '?')}")

        elif args.action == "vidsettings":
            resp = c.request("GetVideoSettings")
            print(f"Base: {resp.get('baseCX', '?')}x{resp.get('baseCY', '?')}")
            print(f"Output: {resp.get('outputCX', '?')}x{resp.get('outputCY', '?')}")
            print(f"FPS: {resp.get('fps', '?')}")
            print(f"Scaler: {resp.get('scalingFilter', '?')}")

        elif args.action == "inputs":
            resp = c.request("GetInputList")
            names = resp.get("inputNames", [])
            print(f"Inputs ({len(names)}):")
            for n in names:
                print(f"  - {n}")


def cmd_transitions(args):
    with _connect() as c:
        if args.action == "list":
            resp = c.request("GetTransitionList")
            trans = resp.get("transitionList", [])
            current = resp.get("currentTransitionName", "?")
            print(f"Current: {current}\n")
            for t in trans:
                name = t if isinstance(t, str) else t.get("name", "?")
                marker = " ◀" if name == current else ""
                print(f"  - {name}{marker}")

        elif args.action == "set":
            if not args.name:
                print("ERROR: transition name required", file=sys.stderr)
                return
            c.request("SetCurrentSceneTransition", {"transitionName": args.name})
            print(f"Transition: {args.name}")

        elif args.action == "duration":
            if not args.duration:
                print("ERROR: duration (ms) required", file=sys.stderr)
                return
            c.request("SetTransitionDuration", {"duration": int(args.duration)})
            print(f"Duration: {args.duration}ms")

        elif args.action == "trigger":
            c.request("TriggerStudioModeTransition")
            print("Transition triggered")


def cmd_screenshot(args):
    with _connect() as c:
        fmt = args.format or "png"
        w = args.width or 1920
        h = args.height or 1080

        if args.type == "scene":
            if not args.name:
                print("ERROR: scene name required", file=sys.stderr)
                return
            resp = c.request("GetSceneScreenshot", {
                "sceneName": args.name,
                "imageWidth": w,
                "imageHeight": h,
                "imageFormat": fmt,
            })
        else:  # source
            if not args.name:
                print("ERROR: source name required", file=sys.stderr)
                return
            resp = c.request("GetSourceScreenshot", {
                "sourceName": args.name,
                "imageWidth": w,
                "imageHeight": h,
                "imageFormat": fmt,
            })

        data = resp.get("imageData", "")
        if data:
            safe = args.name.replace(" ", "_")
            out = Path("~/Desktop").expanduser() / f"obs_{args.type}_{safe}.{fmt}"
            out.write_bytes(base64.b64decode(data))
            print(f"Saved: {out}")
        else:
            print("ERROR: No image data received", file=sys.stderr)


def cmd_inputs(args):
    with _connect() as c:
        if args.action == "list":
            resp = c.request("GetInputList")
            names = resp.get("inputNames", [])
            print(f"Inputs ({len(names)}):")
            for n in names:
                print(f"  - {n}")

        elif args.action == "settings":
            if not args.name:
                print("ERROR: input name required", file=sys.stderr)
                return
            resp = c.request("GetInputSettings", {"inputName": args.name})
            print(json.dumps(resp, indent=2))

        elif args.action == "set":
            if not args.name or not args.json:
                print("ERROR: input name and --json required", file=sys.stderr)
                return
            settings = json.loads(args.json)
            c.request("SetInputSettings", {
                "inputName": args.name,
                "inputSettings": settings,
            })
            print(f"Settings updated: {args.name}")


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="obsctl",
        description="OBS Studio WebSocket Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  obsctl scenes list
  obsctl scenes switch --scene "Game"
  obsctl recording start
  obsctl sources mute --source "Discord" --mute true
  obsctl sources volume --source "Mic" --volume 0.7
  obsctl system stats
  obsctl screenshot scene --name "Desktop" --format jpg
  obsctl transitions set --name "Cut"
""",
    )
    parser.add_argument("--host", default=None, help=f"OBS host (default: {OBS_HOST})")
    parser.add_argument("--port", type=int, default=None, help=f"OBS port (default: {OBS_PORT})")
    parser.add_argument("--password", default=None, help="OBS password")

    sub = parser.add_subparsers(dest="category")

    # scenes
    p = sub.add_parser("scenes", help="Scene management")
    p.add_argument("action", choices=["list", "switch", "create", "delete"])
    p.add_argument("--scene", default=None, help="Scene name")
    p.set_defaults(func=cmd_scenes)

    # sources
    p = sub.add_parser("sources", help="Source control")
    p.add_argument("action", choices=["list", "visible", "volume", "mute"])
    p.add_argument("--scene", default=None, help="Scene name")
    p.add_argument("--source", default=None, help="Source/input name")
    p.add_argument("--visible", type=_bool, default=None, help="Visibility (true/false)")
    p.add_argument("--volume", type=float, default=None, help="Volume 0.0-1.0")
    p.add_argument("--mute", type=_bool, default=None, help="Mute state (true/false)")
    p.set_defaults(func=cmd_sources)

    # recording
    p = sub.add_parser("recording", help="Recording control")
    p.add_argument("action", choices=["start", "stop", "pause", "resume", "status"])
    p.set_defaults(func=cmd_recording)

    # streaming
    p = sub.add_parser("streaming", help="Streaming control")
    p.add_argument("action", choices=["start", "stop", "status"])
    p.set_defaults(func=cmd_streaming)

    # replay
    p = sub.add_parser("replay", help="Replay buffer")
    p.add_argument("action", choices=["start", "stop", "save"])
    p.set_defaults(func=cmd_replay)

    # system
    p = sub.add_parser("system", help="System info")
    p.add_argument("action", choices=["version", "stats", "vidsettings", "inputs"])
    p.set_defaults(func=cmd_system)

    # transitions
    p = sub.add_parser("transitions", help="Transitions")
    p.add_argument("action", choices=["list", "set", "duration", "trigger"])
    p.add_argument("--name", default=None, help="Transition name")
    p.add_argument("--duration", type=int, default=None, help="Duration in ms")
    p.set_defaults(func=cmd_transitions)

    # screenshot
    p = sub.add_parser("screenshot", help="Capture screenshots")
    p.add_argument("type", choices=["scene", "source"])
    p.add_argument("--name", default=None, help="Scene/source name")
    p.add_argument("--format", default="png", help="Image format (png/jpg)")
    p.add_argument("--width", type=int, default=1920, help="Width")
    p.add_argument("--height", type=int, default=1080, help="Height")
    p.set_defaults(func=cmd_screenshot)

    # inputs
    p = sub.add_parser("inputs", help="Input management")
    p.add_argument("action", choices=["list", "settings", "set"])
    p.add_argument("--name", default=None, help="Input name")
    p.add_argument("--json", default=None, help="Settings JSON string")
    p.set_defaults(func=cmd_inputs)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Apply CLI overrides
    if args.host:
        global OBS_HOST
        OBS_HOST = args.host
    if args.port:
        global OBS_PORT
        OBS_PORT = args.port
    if args.password:
        global OBS_PASS
        OBS_PASS = args.password

    if not args.category:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except ConnectionError as e:
        print(f"\u274c {e}", file=sys.stderr)
        sys.exit(2)
    except ObsError as e:
        print(f"\u274c OBS error: {e}", file=sys.stderr)
        sys.exit(3)
    except TimeoutError as e:
        print(f"\u274c Timeout: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
