#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python_bin="${PYTHON:-python3}"
"$python_bin" -c 'import sys; assert sys.version_info >= (3, 10)' || {
  echo 'Python 3.10 or newer is required (set PYTHON to choose one).' >&2
  exit 1
}
if [[ ! -x .venv/bin/python ]]; then
  "$python_bin" -m venv .venv
fi

command -v swiftc >/dev/null || { echo 'Install Xcode Command Line Tools first.' >&2; exit 1; }
sdk_dir="$(xcrun --sdk macosx --show-sdk-path)"
module_cache="${TMPDIR:-/tmp}/swiftbar-zukka-module-cache"
mkdir -p "$module_cache"
build_app() {
  local app="$1" source="$2" plist="$3" executable="$4"
  local binary="$app/Contents/MacOS/$executable"
  local info="$app/Contents/Info.plist"
  if [[ -x "$binary" && ! "$source" -nt "$binary" && ! "$plist" -nt "$info" ]]; then
    return
  fi
  mkdir -p "$app/Contents/MacOS"
  cp "$plist" "$info"
  CLANG_MODULE_CACHE_PATH="$module_cache" swiftc -sdk "$sdk_dir" \
    -target "$(uname -m)-apple-macosx14.0" \
    -module-cache-path "$module_cache" "$source" -o "$binary"
  codesign --force --sign - "$app"
}
build_app .scripts/GlucoseCalendarReader.app \
  .scripts/glucose_calendar.swift .scripts/glucose_calendar.plist GlucoseCalendarReader
build_app .scripts/GlucoseNotifier.app \
  .scripts/glucose_notifier.swift .scripts/glucose_notifier.plist GlucoseNotifier
chmod +x plugin.py
echo 'Ready. Copy this .swiftbar package into SwiftBar’s plugin folder and refresh SwiftBar.'
