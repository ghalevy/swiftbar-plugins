"""Reject known runtime health files and common private markers before publication."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
forbidden_names = {
    "glucose_history.json", "glucose_readings_cache.txt", "glucose_alerts.json",
    "glucose_alert_state.json", "glucose_reader.pid", "glucose_reader_launch.txt",
}
private = re.compile(r"/Users/[^/\s]+|https?://[^\s]+\.internal\b|(?:api[_-]?key|password|token)\s*[:=]\s*[^\s#]+", re.I)
errors = []
reviewed_media = {
    Path("plugins/zukka-cgm/media/menu-demo.png"),
    Path("plugins/zukka-cgm/media/alerts-menu-demo.png"),
    Path("plugins/zukka-cgm/media/walk-suggestion-demo.png"),
    Path("plugins/zukka-cgm/media/zukka-demo.gif"),
}
for path in root.rglob("*"):
    if (any(part in {".git", ".venv", "__pycache__"} or part.endswith(".app")
            for part in path.parts)
            or path == Path(__file__).resolve() or not path.is_file()):
        continue
    if path.name in forbidden_names or path.suffix in {".pyc", ".p12", ".key"}:
        errors.append(f"runtime or key file: {path.relative_to(root)}")
        continue
    relative = path.relative_to(root)
    if relative in reviewed_media:
        signature = b"\x89PNG\r\n\x1a\n" if path.suffix == ".png" else b"GIF8"
        if not path.read_bytes().startswith(signature) or path.stat().st_size > 2_000_000:
            errors.append(f"invalid reviewed media: {relative}")
        continue
    try:
        text = path.read_text()
    except (UnicodeError, OSError):
        errors.append(f"non-text file requires manual review: {path.relative_to(root)}")
        continue
    if private.search(text):
        errors.append(f"private marker: {path.relative_to(root)}")
if errors:
    print("\n".join(errors), file=sys.stderr)
    raise SystemExit(1)
print("Public file check passed")
