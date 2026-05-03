# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository purpose

Sample/community Python scripts and documentation for the **LumiCube** (Raspberry Pi LED cube kit by Abstract Foundry). This repo does **not** contain the daemon/runtime — that lives in `abstractfoundry/lumicube-daemon`. Scripts here are consumed by the LumiCube daemon's web IDE or sent to it over its REST API.

## Two execution contexts (critical distinction)

Scripts in this repo run in one of two very different environments. Misidentifying which is which will produce broken code.

### 1. On-cube scripts (`examples/`, most of `community-scripts/`)

Run **inside** the LumiCube daemon's Python sandbox (web IDE or `POST /api/v1/scripts/main/methods/start`). The daemon injects module globals — these are NOT importable, NOT defined anywhere in this repo, and must NOT be re-imported:

- Modules: `display`, `screen`, `speaker`, `microphone`, `buttons`, `imu`, `light_sensor`, `clock`, `pi`, `env`
- Helpers: `hsv_colour`, `rgb_colour`, named colour constants (`red`, `blue`, …)
- Standard libs like `time`, `math`, `random` are pre-imported as globals

Example (`examples/rainbow.py`) — note no imports, no `if __name__`:

```python
hue = 0
while True:
    hue += 0.01
    if hue > 1: hue = 0
    display.set_all(hsv_colour(hue, 1, 1))
    time.sleep(1 / 30)
```

When adding/editing on-cube scripts, mirror this style: top-level code, no shebang, no imports of cube modules. The full module/method/field surface is documented in `official-documentation/api.txt` and `official-documentation/manual.txt` — read these before guessing an API.

### 2. Off-cube scripts (run on a normal host)

These talk to one or more cubes over HTTP. They DO use normal imports (`requests`, etc.) and have `if __name__ == "__main__"`. The two in this repo:

- `community-scripts/cube_runner.py` — rotates scripts across multiple cubes on a schedule by POSTing each `.py` file body to `/api/v1/scripts/main/methods/start`. Config is an in-file `config` dict (see file header). Assumes scripts live at `/home/pi/AbstractFoundry/Daemon/Scripts/` on each pi.
- `community-scripts/Lumicube Interface/LumicubeInterface.py` — a typed Python wrapper around the REST API for use from a non-cube host.

## REST API (used by off-cube scripts)

Base: `http://<cube-host>/api/v1`

- Field GET/POST: `/modules/<module>/fields/<field>` body `{"value": ...}`
- Method call:   `/modules/<module>/methods/<method>` body `{"arguments": [...]}`
- Run script:    `/scripts/main/methods/start` body `{"body": "<python source>"}`
- Stop script:   `/scripts/main/methods/stop`
- Tuple coords (e.g. `set_leds`, `set_3d`) are sent as comma-separated string keys: `{"0,0": 128, "1,1": 255}` — JSON has no tuple type.

## Running things

There is no build, no test suite, no package layout. Each `.py` is standalone.

- On-cube: paste/upload the file to the cube's web IDE, or POST it via the REST API.
- Off-cube (`cube_runner.py`, etc.): `C:/Python312/python.exe community-scripts/cube_runner.py` (this machine's harness needs the full python path — see the user CLAUDE.md note about stripped PATH).

## Conventions when adding scripts

- New on-cube scripts go in `community-scripts/` (or `examples/` if you're maintaining the curated set). Keep them single-file and self-contained.
- Don't add `requirements.txt` or package scaffolding — the daemon's sandbox already provides what's available, and off-cube scripts only use stdlib + `requests`.
- The README's "Example projects" section is hand-curated — if you add to `examples/`, also add a short blurb there.
