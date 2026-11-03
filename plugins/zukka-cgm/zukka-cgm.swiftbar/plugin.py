#!/bin/sh
# <xbar.title>Zukka CGM Calendar</xbar.title>
# <xbar.version>v1.0.0</xbar.version>
# <xbar.author>Gilad Halevy</xbar.author>
# <xbar.author.github>ghalevy</xbar.author.github>
# <xbar.desc>Show Zukka Calendar Share readings, trends, and age.</xbar.desc>
# <swiftbar.schedule>* * * * *</swiftbar.schedule>
""":"
exec "$(dirname "$0")/.venv/bin/python" -B "$0" "$@"
":"""
"""Show recent Zukka Calendar Share readings from a dedicated Mac calendar."""

import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


CALENDAR_NAME = os.environ.get("GLUCOSE_CALENDAR", "Glucose")
DEMO_MODE = os.environ.get("ZUKKA_CGM_DEMO") == "1"
STALE_AFTER_SECONDS = 15 * 60
READER = Path(__file__).resolve().parent / ".scripts/GlucoseCalendarReader.app"
NOTIFIER = Path(__file__).resolve().parent / ".scripts/GlucoseNotifier.app"
SCRIPT = Path(__file__).resolve()
CONFIG_FILE = SCRIPT.parent / ".scripts/glucose_alerts.json"
STATE_FILE = SCRIPT.parent / ".scripts/glucose_alert_state.json"
LOCK_FILE = SCRIPT.parent / ".scripts/glucose_alert_state.lock"
PAUSE_FILE = SCRIPT.parent / ".scripts/glucose_pause"
CACHE_FILE = SCRIPT.parent / ".scripts/glucose_readings_cache.txt"
READER_PID_FILE = SCRIPT.parent / ".scripts/glucose_reader.pid"
READER_LAUNCH_FILE = SCRIPT.parent / ".scripts/glucose_reader_launch.txt"
HISTORY_FILE = SCRIPT.parent / ".scripts/glucose_history.json"
READING = re.compile(r"(?<!\d)(\d{2,3})\s*([↑↗→↘↓])")
INDICATOR_LEVELS = {"🟢": "good", "🟡": "warning", "🟠": "warning", "🔴": "danger"}
INDICATOR_COLORS = {
    "🟢": "#34C759",
    "🟡": "#FFCC00",
    "🟠": "#FFCC00",
    "🔴": "#FF3B30",
}
DEFAULT_ALERTS = {
    "enabled": False,
    "warning": True,
    "danger": True,
    "spike": True,
    "focus_override": False,
    "rise_rate": 2.0,
    "cooldown_minutes": 30,
}


def clean(value):
    """Keep calendar text from becoming SwiftBar syntax or extra menu rows."""
    return value.replace("|", "¦").replace("\r", " ").replace("\n", " ").strip()


def age_label(seconds):
    seconds = max(0, seconds)
    if seconds < 60:
        return "<1m"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def level_from_title(title):
    """Use Zukka's range indicator, without guessing glucose thresholds."""
    before_reading = title[:READING.search(title).start()]
    return next((level for indicator, level in INDICATOR_LEVELS.items()
                 if indicator in before_reading), None)


def color_from_title(title):
    level = level_from_title(title)
    return next((INDICATOR_COLORS[indicator] for indicator, name in INDICATOR_LEVELS.items()
                 if name == level), None)


def load_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
        json.dump(value, tmp)
        temp_path = Path(tmp.name)
    os.chmod(temp_path, 0o600)
    os.replace(temp_path, path)


def record_history(readings):
    """Keep distinct Calendar readings for charts without relaunching EventKit."""
    now = time.time()
    cutoff = now - 8 * 86400
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        saved = load_json(HISTORY_FILE)
        samples = saved.get("samples", []) if isinstance(saved, dict) else []
        by_minute = {}
        for sample in samples:
            if (isinstance(sample, list) and len(sample) == 2
                    and all(isinstance(item, (int, float)) for item in sample)):
                minute, value = sample
                if cutoff <= minute <= now and 20 <= value <= 600:
                    by_minute[int(minute)] = int(value)
        original = dict(by_minute)
        for age, _, value, _ in readings:
            minute = int((now - age) // 60) * 60
            if cutoff <= minute <= now:
                by_minute[minute] = int(value)
        if by_minute != original or not HISTORY_FILE.exists():
            save_json(HISTORY_FILE, {"samples": sorted([minute, value]
                                                      for minute, value in by_minute.items())})
        return sorted(by_minute.items())


def chart_line(samples, start, end, width=44):
    """Return a time-aligned sparkline, leaving gaps where no readings exist."""
    buckets = [[] for _ in range(width)]
    for timestamp, value in samples:
        if start <= timestamp <= end:
            column = min(width - 1, int((timestamp - start) / (end - start) * width))
            buckets[column].append(value)
    values = [value for bucket in buckets for value in bucket]
    if not values:
        return "·" * width, None, None, 0
    low, high = min(values), max(values)
    blocks = "▁▂▃▄▅▆▇█"
    scale = max(20, high - low)
    base = (high + low - scale) / 2
    chart = "".join(blocks[min(7, max(0, round((bucket[-1] - base) / scale * 7)))]
                    if bucket else "·" for bucket in buckets)
    return chart, low, high, len(values)


def history_menu(samples):
    now = time.time()
    print("---")
    print("Glucose history | sfimage=chart.xyaxis.line color=secondaryLabel")
    for label, duration in (("Past 24h", 86400), ("Past 7 days", 7 * 86400)):
        chart, low, high, count = chart_line(samples, now - duration, now)
        print(f"{label}  {chart} | font=Menlo size=11")
        if count:
            print(f"--{count} readings · {low}–{high} mg/dL | color=secondaryLabel size=11")
        else:
            print("--Collecting readings | color=secondaryLabel size=11")
    if samples and samples[0][0] > now - 7 * 86400:
        started = datetime.fromtimestamp(samples[0][0]).strftime("%b %-d")
        print(f"History starts {started}; the week chart fills over time | color=secondaryLabel size=11")


def load_alerts():
    saved = load_json(CONFIG_FILE)
    return {**DEFAULT_ALERTS, **{key: saved[key] for key in DEFAULT_ALERTS if key in saved}}


def configure_alerts(args):
    if len(args) != 2:
        return
    action, key = args
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = load_alerts()
        if action == "toggle" and key in ("enabled", "warning", "danger", "spike", "focus_override"):
            config[key] = not config[key]
        elif action == "rise_rate" and key in ("1.5", "2.0", "3.0"):
            config["rise_rate"] = float(key)
        elif action == "cooldown_minutes" and key in ("15", "30", "60"):
            config["cooldown_minutes"] = int(key)
        else:
            return
        save_json(CONFIG_FILE, config)


def spike_detected(readings, rise_rate):
    age, _, value, trend = readings[0]
    if trend in ("↗", "↑"):
        return True
    current = int(value)
    for prior_age, _, prior_value, _ in readings[1:]:
        gap_minutes = (prior_age - age) / 60
        rise = current - int(prior_value)
        if 4 <= gap_minutes <= 15 and rise >= 10 and rise / gap_minutes >= rise_rate:
            return True
    return False


def send_notification(title, body, urgent=False):
    if not NOTIFIER.exists():
        return False
    try:
        with tempfile.TemporaryDirectory(prefix="swiftbar-glucose-notify-") as tmp:
            output = Path(tmp) / "result.txt"
            subprocess.run(
                ["/usr/bin/open", "-W", "-n", "-a", str(NOTIFIER), "--args",
                 str(output), title, body, "urgent" if urgent else "normal"],
                capture_output=True, timeout=30, check=False,
            )
            return output.exists() and output.read_text().strip() == "NOTIFICATION_SENT"
    except (OSError, subprocess.SubprocessError):
        return False


def maybe_alert(readings, config):
    if not config["enabled"] or readings[0][0] >= 10 * 60:
        return None
    age, title, value, trend = readings[0]
    level = level_from_title(title)
    spike = config["spike"] and level != "danger" and 100 <= int(value) < 240 \
        and spike_detected(readings, config["rise_rate"])
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_json(STATE_FILE)
        now = time.time()
        cooldown = config["cooldown_minutes"] * 60
        ready = lambda kind: now - state.get(kind, 0) >= cooldown
        kinds = []
        if level == "danger" and config["danger"] and ready("danger"):
            heading = "Zukka glucose alert"
            message = f"{value} mg/dL {trend} · red range. Check your primary CGM app."
            kinds = ["danger"]
        elif level == "warning" and config["warning"] and ready("warning"):
            heading = "Zukka glucose warning"
            message = f"{value} mg/dL {trend} · yellow range."
            kinds = ["warning"]
            if spike and ready("spike"):
                message += " Rising quickly—consider a short walk if it is safe for you."
                kinds.append("spike")
        elif spike and ready("spike"):
            heading = "Glucose rising"
            message = f"{value} mg/dL {trend} · Consider a short walk if it is safe for you."
            kinds = ["spike"]
        if not kinds:
            return None
        urgent = config["focus_override"] and kinds[0] in ("warning", "danger")
        if not send_notification(heading, message, urgent=urgent):
            return "Mac notification could not be sent"
        for kind in kinds:
            state[kind] = now
        save_json(STATE_FILE, state)
    return None


def alert_menu(config):
    script = str(SCRIPT)
    print("---")
    print("Alerts · Zukka Calendar Share | color=secondaryLabel")
    for key, label in (("enabled", "Alerts enabled"), ("warning", "Yellow warning"),
        ("danger", "Red danger"), ("spike", "Walk prompt on spike"),
                       ("focus_override", "Red/yellow through Focus")):
        checked = str(config[key]).lower()
        print(f"{label} | checked={checked} bash={script} param1=toggle param2={key} "
              "terminal=false refresh=true")
    print(f"Spike sensitivity · {config['rise_rate']:g} mg/dL/min")
    for rate in (1.5, 2.0, 3.0):
        checked = str(config["rise_rate"] == rate).lower()
        print(f"--{rate:g} mg/dL/min | checked={checked} bash={script} "
              f"param1=rise_rate param2={rate:.1f} terminal=false refresh=true")
    print(f"Repeat alerts after · {config['cooldown_minutes']} min")
    for minutes in (15, 30, 60):
        checked = str(config["cooldown_minutes"] == minutes).lower()
        print(f"--{minutes} min | checked={checked} bash={script} "
              f"param1=cooldown_minutes param2={minutes} terminal=false refresh=true")
    print(f"Test red/yellow popup | bash={script} param1=test param2=urgent terminal=false")
    print(f"Test walk notification | bash={script} param1=test param2=normal terminal=false")


def get_readings():
    if not READER.exists():
        raise FileNotFoundError(READER)
    ensure_reader_running()
    try:
        data = CACHE_FILE.read_text()
        cache_age = max(0, int(time.time() - CACHE_FILE.stat().st_mtime))
    except FileNotFoundError:
        data = ""
        cache_age = 0
    if data.strip() == "CALENDAR_ACCESS_DENIED":
        raise PermissionError("Calendar access denied")
    if data.strip() == "CALENDAR_NOT_FOUND":
        return None
    if not data:
        raise ReaderStarting()
    readings = []
    for line in data.splitlines():
        try:
            title, age = line.rsplit("\t", 1)
            age = int(age) + cache_age
        except ValueError:
            continue
        match = READING.search(title)
        if match and -300 <= age < 86400:
            readings.append((max(0, age), clean(title), match.group(1), match.group(2)))
    return sorted(readings, key=lambda item: item[0])


class ReaderStarting(Exception):
    pass


def reader_running():
    try:
        pid = int(READER_PID_FILE.read_text().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def ensure_reader_running():
    if reader_running():
        return
    with LOCK_FILE.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if reader_running():
            return
        try:
            last_launch = float(READER_LAUNCH_FILE.read_text())
        except (OSError, ValueError):
            last_launch = 0
        if time.time() - last_launch < 120:
            return
        READER_LAUNCH_FILE.write_text(str(time.time()))
        result = subprocess.run(
            ["/usr/bin/open", "-n", "-a", str(READER), "--args", "watch",
             CALENDAR_NAME, str(CACHE_FILE), str(READER_PID_FILE)],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Calendar reader did not launch ({result.returncode})")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "test" and sys.argv[2] in ("urgent", "normal"):
        urgent = sys.argv[2] == "urgent"
        title = "Zukka glucose alerts" if urgent else "Glucose rising · test"
        body = ("Synthetic test notification from SwiftBar" if urgent else
                "Synthetic test: Consider a short walk if it is safe for you.")
        if not send_notification(title, body, urgent):
            print("Could not send Mac notification", file=sys.stderr)
            raise SystemExit(1)
        return
    if sys.argv[1:]:
        configure_alerts(sys.argv[1:])
        return
    if not DEMO_MODE and PAUSE_FILE.exists():
        print("Glucose reader updating | color=orange")
        return
    config = DEFAULT_ALERTS.copy() if DEMO_MODE else load_alerts()
    try:
        readings = ([(120, "🟢 128 →", "128", "→"),
                     (420, "🟢 125 ↗", "125", "↗"),
                     (720, "🟢 119 →", "119", "→")]
                    if DEMO_MODE else get_readings())
    except ReaderStarting:
        print("Glucose starting… | sfimage=drop.fill color=orange")
        print("---")
        print("Calendar reader is starting")
        return
    except PermissionError:
        print("Glucose ? | sfimage=drop.fill color=orange")
        print("---")
        print("Calendar access denied; check System Settings → Privacy & Security → Calendars")
        return
    except FileNotFoundError:
        print("Glucose setup")
        print("---")
        print("Run bash .scripts/setup.sh, then refresh")
        return
    except RuntimeError:
        print("Glucose ?")
        print("---")
        print("Could not launch Calendar reader | color=orange")
        return
    except (OSError, subprocess.SubprocessError):
        print("Glucose ?")
        print("---")
        print("Could not read Calendar; check Calendar access in System Settings | color=orange")
        print("Refresh | refresh=true")
        return

    if readings is None:
        print("Glucose ?")
        print("---")
        print(f"Calendar not found: {clean(CALENDAR_NAME)} | color=orange")
        return
    if not readings:
        print("Glucose —")
        print("---")
        print(f"No recent readings in {clean(CALENDAR_NAME)} | color=orange")
        print("Refresh | refresh=true")
        return

    history = ([(int(time.time()) - age, int(value)) for age, _, value, _ in readings]
               if DEMO_MODE else record_history(readings))
    alert_error = None if DEMO_MODE else maybe_alert(readings, config)
    age, title, value, trend = readings[0]
    if age >= STALE_AFTER_SECONDS:
        print(f"Glucose stale · {age_label(age)} | sfimage=drop.fill color=orange")
    else:
        color = color_from_title(title)
        style = "sfimage=drop.fill"
        if color:
            style += f" color={color}"
        prefix = "DEMO · " if DEMO_MODE else ""
        print(f"{prefix}{value} {trend} · {age_label(age)} | {style}")
    print("---")
    if DEMO_MODE:
        print("Synthetic demo data · no calendar access or notifications | color=orange")
    print("Zukka · Calendar Share | color=secondaryLabel")
    print(f"Latest: {title} · {age_label(age)} old")
    if age >= STALE_AFTER_SECONDS:
        print("Calendar reading is stale | color=orange")
    if len(readings) > 1:
        print("---")
        for prior_age, prior_title, _, _ in readings[1:6]:
            print(f"{prior_title} · {age_label(prior_age)} old")
    history_menu(history)
    if not DEMO_MODE:
        alert_menu(config)
    if alert_error:
        print(f"{alert_error} | color=orange")
    print("---")
    print("Refresh | refresh=true")


if __name__ == "__main__":
    main()
