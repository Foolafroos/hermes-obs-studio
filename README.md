# hermes-obs-studio

Control [OBS Studio](https://obsproject.com/) from the command line via its built-in WebSocket API.

Designed as a skill for [Hermes Agent](https://github.com/nousresearch/hermes-agent) — but works standalone too.

## Features

| Category | Actions |
|---|---|
| **Scenes** | list, switch, create, delete |
| **Sources** | list, toggle visibility, volume, mute |
| **Recording** | start, stop, pause, resume, status |
| **Streaming** | start, stop, status |
| **Replay Buffer** | start, stop, save |
| **Transitions** | list, set, duration, trigger |
| **System** | version, stats, video settings, inputs |
| **Screenshots** | capture scene or source to PNG/JPG |
| **Inputs** | list, get/set settings |

## Quick Start

### 1. Enable OBS WebSocket Server

Open OBS → **Settings** → **Advanced** → **WebSocket Server Settings**:
- ✅ Enable WebSocket Server
- Port: `4444` (default)
- Optional: set a password
- Click **OK**

### 2. Install dependencies

```bash
pip3 install websocket-client
```

### 3. Verify connection

```bash
python3 scripts/preflight.py
```

### 4. Use it

```bash
# List scenes
python3 scripts/obsctl.py scenes list

# Switch to a scene
python3 scripts/obsctl.py scenes switch --scene "Game"

# Start recording
python3 scripts/obsctl.py recording start

# Check stats
python3 scripts/obsctl.py system stats

# Mute a source
python3 scripts/obsctl.py sources mute --source "Discord" --mute true

# Set volume
python3 scripts/obsctl.py sources volume --source "Mic" --volume 0.7

# Screenshot a scene
python3 scripts/obsctl.py screenshot scene --name "Desktop"
```

See [full help](https://github.com/Foolafroos/hermes-obs-studio/blob/main/scripts/obsctl.py) or run `python3 scripts/obsctl.py --help`.

## Configuration

### Environment variables (recommended)

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
```

```env
OBS_WS_HOST=127.0.0.1
OBS_WS_PORT=4444
OBS_WS_PASSWORD=
```

### CLI overrides

```bash
python3 scripts/obsctl.py --host 127.0.0.1 --port 4444 --password mypass scenes list
```

## Hermes Agent Integration

Drop the `scripts/` directory into your Hermes skills folder and load this skill. The agent will use `obsctl.py` to control OBS on your behalf.

**Natural language examples:**
- "Switch OBS to my camera scene"
- "Start recording in OBS"
- "Mute the Discord source"
- "What are my OBS stats?"
- "Save the replay buffer"

## Architecture

```
┌─────────────┐     WebSocket      ┌──────────────────┐
│  Hermes     │ ──────────────────▶ │  OBS Studio      │
│  Agent      │   ws://localhost   │  (WebSocket v5)  │
│             │ ◀────────────────── │  port 4444       │
│  obsctl.py  │   JSON responses   │                  │
└─────────────┘                    └──────────────────┘
```

- **Zero daemon** — connects, does the thing, disconnects
- **Zero Node.js** — pure Python, one dependency (`websocket-client`)
- **Protocol v5 native** — no wrapper library that breaks on OBS updates

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Usage error |
| 2 | Connection error (OBS not running / WebSocket disabled) |
| 3 | OBS returned an error |
| 4 | Request timeout |

## Requirements

- Python 3.9+
- OBS Studio 30+ (WebSocket plugin built-in)
- `websocket-client` Python package

## License

MIT — see [LICENSE](LICENSE)

## Contributing

Issues and PRs welcome. Please test against your OBS version before submitting.
