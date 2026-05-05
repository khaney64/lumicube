"""Remote LumiCube GPU utilization, VRAM, and temperature display.

Examples:
    python gpu_usage_chart_remote.py --cube lumipi.lan --delay 5
    python gpu_usage_chart_remote.py --cube lumipi.lan --demo --steps 24 --delay 0.35
    python gpu_usage_chart_remote.py --dry-run --once-util 100 --once-vram 25 --once-temp 45
"""

import argparse
import math
import subprocess
import sys
import time

import requests


BLACK = 0x000000
DEFAULT_DEMO_VALUES = [
    (0, 10, 35),
    (8, 20, 42),
    (20, 35, 50),
    (35, 50, 58),
    (55, 65, 66),
    (75, 80, 74),
    (95, 95, 82),
    (60, 70, 68),
    (30, 45, 55),
    (10, 20, 43),
]


def rgb(red, green, blue):
    red = max(0, min(255, int(red)))
    green = max(0, min(255, int(green)))
    blue = max(0, min(255, int(blue)))
    return (red << 16) | (green << 8) | blue


def lerp(a, b, amount):
    return a + (b - a) * amount


def interpolate_color(stops, value):
    value = max(0.0, min(1.0, value))
    for index in range(len(stops) - 1):
        left_pos, left_color = stops[index]
        right_pos, right_color = stops[index + 1]
        if value <= right_pos:
            span = right_pos - left_pos
            amount = 0.0 if span == 0 else (value - left_pos) / span
            return rgb(
                lerp(left_color[0], right_color[0], amount),
                lerp(left_color[1], right_color[1], amount),
                lerp(left_color[2], right_color[2], amount),
            )
    return rgb(*stops[-1][1])


def usage_to_height(percent):
    percent = max(0.0, min(100.0, float(percent)))
    if percent <= 0:
        return 0
    return max(1, min(8, int(math.ceil(percent / 100.0 * 8))))


def color_for_usage_level(y, percent):
    height = usage_to_height(percent)
    if height <= 1:
        return rgb(0, 40, 180)
    active_gradient = [
        rgb(0, 150, 45),
        rgb(70, 185, 35),
        rgb(145, 210, 20),
        rgb(220, 220, 0),
        rgb(255, 190, 0),
        rgb(255, 130, 0),
        rgb(255, 65, 0),
        rgb(255, 0, 0),
    ]
    return active_gradient[max(0, min(7, int(y)))]


def color_for_temperature(temp_c):
    temp_c = float(temp_c)
    if temp_c > 65.0:
        return rgb(255, 0, 0)

    value = (max(30.0, min(65.0, temp_c)) - 30.0) / 35.0
    return interpolate_color(
        [
            (0.00, (0, 80, 255)),
            (0.38, (0, 220, 120)),
            (0.68, (255, 225, 0)),
            (1.00, (255, 135, 0)),
        ],
        value,
    )


def all_visible_leds(color=BLACK):
    leds = {}
    for y in range(8):
        for x in range(16):
            leds[f"{x}, {y}"] = color
    for y in range(8, 16):
        for x in range(8):
            leds[f"{x}, {y}"] = color
    return leds


def draw_usage_chart(leds, columns):
    for x, percent in enumerate(columns[-16:]):
        height = usage_to_height(percent)
        for y in range(height):
            leds[f"{x}, {y}"] = color_for_usage_level(y, percent)


def draw_vram_top(leds, vram_percent, temp_c):
    vram_percent = max(0.0, min(100.0, float(vram_percent)))
    max_distance = math.sqrt(2 * (3.5**2))
    radius = (vram_percent / 100.0) * max_distance
    if vram_percent > 0:
        radius = max(radius, 0.75)
    color = color_for_temperature(temp_c)

    for top_y in range(8):
        for x in range(8):
            distance = math.sqrt((x - 3.5) ** 2 + (top_y - 3.5) ** 2)
            if distance <= radius:
                leds[f"{x}, {top_y + 8}"] = color


def build_leds(columns, vram_percent=0, temp_c=35):
    leds = all_visible_leds()
    draw_usage_chart(leds, columns)
    draw_vram_top(leds, vram_percent, temp_c)
    return leds


def append_column(columns, percent):
    columns.append(max(0.0, min(100.0, float(percent))))
    if len(columns) > 16:
        del columns[:-16]
    return columns


def sample_gpu(timeout=5):
    command = [
        "nvidia-smi",
        "--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "nvidia-smi failed")

    line = result.stdout.strip().splitlines()[0]
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 4:
        raise RuntimeError(f"unexpected nvidia-smi output: {line}")

    memory_used_mb = float(parts[0])
    memory_total_mb = float(parts[1])
    utilization_pct = float(parts[2])
    temperature_c = float(parts[3])
    vram_percent = 0.0 if memory_total_mb <= 0 else memory_used_mb / memory_total_mb * 100.0

    return {
        "memory_used_mb": memory_used_mb,
        "memory_total_mb": memory_total_mb,
        "utilization_pct": utilization_pct,
        "temperature_c": temperature_c,
        "vram_percent": vram_percent,
    }


def post_set_leds(cube, leds, timeout=5, retries=4):
    url = f"http://{cube}/api/v1/modules/display/methods/set_leds"
    last_error = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(url, json={"arguments": [leds]}, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(min(2.0, 0.5 * (2 ** attempt)))
    raise last_error


def summarize_frame(leds):
    lit = sum(1 for value in leds.values() if value != BLACK)
    return f"{len(leds)} leds, {lit} lit"


def send_or_print(args, leds, metrics):
    summary = summarize_frame(leds)
    metric_text = (
        f"gpu={metrics['utilization_pct']:.1f}% "
        f"vram={metrics['vram_percent']:.1f}% "
        f"({metrics['memory_used_mb']:.0f}/{metrics['memory_total_mb']:.0f} MB) "
        f"temp={metrics['temperature_c']:.1f}C"
    )
    if args.dry_run:
        if not args.quiet:
            print(f"dry-run: {metric_text}; {summary}")
        return True

    try:
        post_set_leds(args.cube, leds, args.timeout, args.retries)
    except requests.RequestException as exc:
        print(f"warning: send to {args.cube} failed, will retry next frame: {exc}", file=sys.stderr)
        return False
    if not args.quiet:
        print(f"sent to {args.cube}: {metric_text}; {summary}")
    return True


def static_metrics(args):
    memory_total = 100.0
    return {
        "memory_used_mb": memory_total * args.once_vram / 100.0,
        "memory_total_mb": memory_total,
        "utilization_pct": args.once_util,
        "temperature_c": args.once_temp,
        "vram_percent": args.once_vram,
    }


def run_once(args):
    metrics = static_metrics(args)
    columns = [metrics["utilization_pct"]]
    leds = build_leds(columns, metrics["vram_percent"], metrics["temperature_c"])
    send_or_print(args, leds, metrics)


def run_demo(args):
    columns = []
    index = 0
    last_leds = None
    while args.steps is None or index < args.steps:
        util, vram, temp = DEFAULT_DEMO_VALUES[index % len(DEFAULT_DEMO_VALUES)]
        index += 1
        append_column(columns, util)
        metrics = {
            "memory_used_mb": vram,
            "memory_total_mb": 100.0,
            "utilization_pct": util,
            "temperature_c": temp,
            "vram_percent": vram,
        }
        leds = build_leds(columns, vram, temp)
        if leds != last_leds:
            if send_or_print(args, leds, metrics):
                last_leds = leds
        time.sleep(args.delay)


def run_live(args):
    columns = []
    index = 0
    last_leds = None
    while args.steps is None or index < args.steps:
        index += 1
        metrics = sample_gpu(args.timeout)
        chart_util = metrics["utilization_pct"]
        if chart_util < args.idle_threshold:
            chart_util = 0.0
        append_column(columns, chart_util)
        leds = build_leds(columns, metrics["vram_percent"], metrics["temperature_c"])
        if leds != last_leds:
            if send_or_print(args, leds, metrics):
                last_leds = leds
        time.sleep(args.delay)


def clear_cube(args):
    if args.dry_run:
        if not args.quiet:
            print("dry-run: cleared")
        return
    try:
        post_set_leds(args.cube, all_visible_leds(BLACK), args.timeout, args.retries)
        if not args.quiet:
            print(f"cleared {args.cube}")
    except Exception as exc:
        print(f"warning: failed to clear {args.cube}: {exc}", file=sys.stderr)


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cube",
        "--host",
        dest="cube",
        default="lumipi.lan",
        help="cube hostname or IP address, default: lumipi.lan",
    )
    parser.add_argument(
        "--delay",
        "--interval",
        dest="delay",
        type=float,
        default=5.0,
        help="seconds between display updates, default: 5",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP/nvidia-smi timeout in seconds")
    parser.add_argument("--retries", type=int, default=4, help="REST retries per frame")
    parser.add_argument("--dry-run", action="store_true", help="print frame summaries without sending to cube")
    parser.add_argument("--quiet", action="store_true", help="suppress per-frame stdout (warnings still go to stderr)")
    parser.add_argument("--demo", action="store_true", help="use synthetic values instead of nvidia-smi")
    parser.add_argument("--steps", type=int, help="number of frames to send before exiting")
    parser.add_argument("--once-util", type=float, help="send one static frame with this GPU utilization percent")
    parser.add_argument("--once-vram", type=float, default=25.0, help="VRAM percent for --once-util")
    parser.add_argument("--once-temp", type=float, default=45.0, help="temperature C for --once-util")
    parser.add_argument(
        "--idle-threshold",
        type=float,
        default=3.0,
        help="GPU utilization percent below which the chart treats the sample as 0, "
             "suppressing scroll-jitter on an idle cube. default: 3",
    )
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.delay < 0:
        parser.error("--delay must be 0 or greater")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.retries < 0:
        parser.error("--retries must be 0 or greater")
    if args.steps is not None and args.steps < 1:
        parser.error("--steps must be 1 or greater")
    if args.idle_threshold < 0:
        parser.error("--idle-threshold must be 0 or greater")

    try:
        if args.once_util is not None:
            run_once(args)
        elif args.demo:
            run_demo(args)
        else:
            run_live(args)
    except KeyboardInterrupt:
        clear_cube(args)


if __name__ == "__main__":
    main(sys.argv[1:])
