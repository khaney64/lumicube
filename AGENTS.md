# LumiCube Code Generation Guide

Use this repository to generate standalone Python scripts that drive a LumiCube display. Start with `CLAUDE.md` for repo context, then check `official-documentation/api.txt` before guessing a display, sensor, or REST API.

## Device Model

The LumiCube is a cube with three visible LED faces. Each visible face has 64 LEDs in an 8x8 grid.

- `left` or `left front`: left front face.
- `right` or `right front`: right front face.
- `top`: top face.

The display can be addressed in either 2D or 3D coordinates.

2D layout:

- Bottom row starts at `(0, 0)` on the bottom-left corner of the left face.
- Bottom row continues through `(15, 0)` on the bottom-right corner of the right face.
- The top face continues at `(0, 8)` through `(7, 15)`.
- Use `display.set_leds(leds)` with a dictionary of `(x, y)` tuple keys when running on-device.

3D layout:

- `(0, 0, 0)` is the bottom-right corner of the left face.
- `(8, 0, 0)` is the bottom-left corner of the right face.
- `(0, 8, 0)` is the top-back corner.
- Common face planes in existing scripts are `z=8` for the left face, `x=8` for the right face, and `y=8` for the top face.
- Use `display.set_3d(leds)` with a dictionary of `(x, y, z)` tuple keys when running on-device.

## Execution Modes

Generated code can be either on-device or remote. Decide which mode the user wants before writing a script.

On-device scripts:

- Run inside the LumiCube daemon's Python sandbox, such as the web IDE or the `/scripts/main/methods/start` REST endpoint.
- Use injected globals. Do not import cube modules from this repo.
- Available globals include `display`, `screen`, `speaker`, `microphone`, `buttons`, `imu`, `light_sensor`, `clock`, `pi`, `env`, `hsv_colour`, `rgb_colour`, named colour constants, and common standard libraries such as `time`, `math`, and `random`.
- Match existing on-device style: top-level script code, no shebang, no `if __name__ == "__main__"` unless an existing script pattern specifically calls for it.
- Use tuple keys directly for `set_leds` and `set_3d` dictionaries.

Remote scripts:

- Run on a normal host machine and drive a cube over HTTP.
- Use the REST API base `http://<cube-host>/api/v1`.
- Use stdlib plus `requests` unless the user explicitly asks for something else.
- Field access uses `/modules/<module>/fields/<field>` with body `{"value": ...}`.
- Method calls use `/modules/<module>/methods/<method>` with body `{"arguments": [...]}`.
- Script execution uses `/scripts/main/methods/start` with body `{"body": "<python source>"}`.
- Stop the running main script with `/scripts/main/methods/stop`.
- JSON has no tuple type. Tuple coordinate keys sent through REST, such as for `set_leds` or `set_3d`, must be comma-separated strings. Existing remote wrapper code uses comma-space keys like `"0, 0"` or `"8, 0, 0"`.
- Direct remote batch display calls work with `POST /api/v1/modules/display/methods/set_leds` and body `{"arguments": [coord_to_colour_dict]}`.

## Reference Scripts

Use grepai or code search before inventing display behavior. Useful examples:

- `community-scripts/cube_runner.py`: remote host script that stops and starts scripts on cube devices through REST.
- `community-scripts/cylon.py`: 3D coordinate animation across left and right faces.
- `community-scripts/vesuvius.py`: 3D face shifting and top-face effects.
- `community-scripts/mlb.py`: HTTP data fetching from an external API.
- `community-scripts/gameday.py`: sports status display using 3D coordinates and scrolling text.
- `community-scripts/nest_thermostat.py`: 3D icon/status display patterns.
- `community-scripts/digital_rain.py`: 2D `set_leds` animation pattern.
- `community-scripts/display_helpers.py`: digit drawing helpers for left and right faces.

## Script Conventions

- Put new standalone scripts in `community-scripts/`.
- Keep scripts self-contained. Do not add package scaffolding or a repo-level `requirements.txt`.
- Prefer the existing display primitives:
  - `display.set_all(colour)` to clear or fill.
  - `display.set_led(x, y, colour)` for one 2D LED.
  - `display.set_leds(x_y_to_colour_dict)` for 2D batches.
  - `display.set_panel(panel, rows)` for one 8x8 face.
  - `display.set_3d(x_y_z_to_colour_dict)` for 3D batches.
- Use `hsv_colour(hue, saturation, value)` or `rgb_colour(red, green, blue)` when running on-device.
- When generating remote scripts that call display methods directly, encode colour values and tuple keys in JSON-compatible forms accepted by the REST API.
- For long-running scripts, include clear timing, bounded update rates, and simple exception handling where the script has network or host dependencies.
- This repo has no build or test suite. Validate generated scripts with syntax checks where possible and by comparing API usage with `official-documentation/api.txt`.
