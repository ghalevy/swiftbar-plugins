# Zukka CGM Calendar for SwiftBar

An unofficial [SwiftBar](https://github.com/swiftbar/SwiftBar) plugin that shows glucose readings already shared to an Apple Calendar by Zukka. It is **not affiliated with or endorsed by Zukka**.

**Convenience display only.** Do not use this plugin in place of your primary CGM app, official glucose monitoring equipment, safety alerts, or medical decision-making. Calendar syncing, SwiftBar refreshes, and Mac notifications can be delayed or fail.

## What it shows

- Latest value in mg/dL, trend arrow, and reading age in the menu bar.
- Green, yellow, or red when the event title contains Zukka's matching range symbol; unknown ranges are left uncolored.
- A conspicuous *stale* label after 15 minutes instead of presenting an old number as current.
- Earlier readings and local 24-hour and seven-day charts, with gaps for intervals not captured on this Mac.
- Optional Mac notifications for yellow or red range indicators and rising readings. All notifications start disabled and have a cooldown; they are not safety alerts.

The plugin reads Calendar through Apple's EventKit. It has **no direct Zukka API integration**, account login, API token, or network client. It does not upload readings. The companion Calendar app or iCloud may sync events separately; see the [Calendar Share documentation](https://xdrip4ios.readthedocs.io/en/latest/services/calendarShare/) for setup and privacy implications.

## Requirements

- macOS 14 or newer, based on the EventKit full-access API used by the helper and its deployment target. The helpers built on macOS 27.0.1; live Calendar behavior, other macOS versions, and Intel Macs have not been tested for this release copy.
- [SwiftBar](https://github.com/swiftbar/SwiftBar), Python 3.10 or newer, Xcode Command Line Tools (`swiftc`, `xcrun`), and `codesign`.
- Zukka Calendar Share writing readings to a dedicated calendar visible in Apple Calendar on this Mac. The plugin expects event titles containing a 2- or 3-digit mg/dL value followed by a trend arrow (`↑ ↗ → ↘ ↓`).

No Python packages or private API access are required.

## Install

1. Enable Calendar Share in Zukka, selecting a dedicated calendar. Avoid using a calendar with personal appointments. Confirm that a recent reading appears in Apple Calendar on your Mac.
2. In `zukka-cgm.swiftbar`, run `bash setup.sh`. This creates a local Python environment and builds the two small Mac helper apps from source.
3. Copy the entire `zukka-cgm.swiftbar` package into your SwiftBar plugin folder. Do not copy only `plugin.py`; it uses the adjacent `.scripts` folder. SwiftBar needs a version that [supports packaged plugins](https://github.com/swiftbar/SwiftBar/blob/main/README-PACKAGED-PLUGINS.md).
4. Refresh SwiftBar. When prompted, allow **SwiftBar Glucose Calendar Reader** full Calendar access. Notification permission is needed only if you enable optional notifications.

The default calendar name is `Glucose`. If yours differs, set `GLUCOSE_CALENDAR` in SwiftBar's process environment and restart SwiftBar. [config.example](config.example) lists the supported environment variables. The plugin saves no credentials.

Setup keeps an existing helper binary when its source and plist have not changed. Rebuilding the Calendar helper can cause macOS to ask for Calendar access again.

## Refresh and local data

SwiftBar runs `plugin.py` every minute using its schedule metadata. The EventKit helper remains open and refreshes its local cache about once a minute. The plugin records distinct readings for eight days of charts. It launches a stopped helper again with a two-minute launch throttle. Use the menu's **Refresh** item to request an immediate SwiftBar refresh.

Runtime data stays inside the package's `.scripts/` directory and is ignored by Git: the reading cache, history, alert settings, cooldown state, and helper process files. Treat this directory and any calendar backup as sensitive health data. The plugin requests full Calendar access because EventKit requires it to read events; select a dedicated calendar and review who can access it. SwiftBar may display recent menu output in its own UI or logs.

## Synthetic demo

Set `ZUKKA_CGM_DEMO=1` for the plugin process and run `./zukka-cgm.swiftbar/plugin.py`. The output uses the real menu rendering path but does not access Calendar, send notifications, or write glucose history. **These are synthetic readings, not real glucose data.** Example first lines:

```text
DEMO · 128 → · 2m
---
Synthetic demo data · no calendar access or notifications
Zukka · Calendar Share
Latest: 🟢 128 → · 2m old
```

No screenshot is included because an authentic live screenshot would reveal personal health data. A future screenshot should be captured from this labeled demo mode in SwiftBar.

## Troubleshooting

| Display | Check |
| --- | --- |
| `Glucose setup` | Run `bash setup.sh` in the package directory. |
| `Calendar access denied` | In macOS Privacy & Security → Calendars, grant the Calendar reader full access. |
| `Calendar not found` | Check the calendar name and that it appears in Apple Calendar on this Mac. |
| `Glucose starting…` | Wait for the EventKit helper's first update, then refresh. |
| `Glucose stale` or `Glucose —` | Check the primary CGM app and Calendar Share sync; do not assume the displayed value is current. |
| Notifications fail | Check Notification permissions for **Zukka Glucose Alerts**. Optional alerts remain disabled by default. |

Calendar Share may provide only the latest event, so charts build as this Mac observes readings and can have gaps. Calendar event titles or range symbols may change between Zukka versions; unsupported formats are ignored. This project does not implement Zukka's account authentication and has no verified compatibility with every CGM source.

## Ownership and license

The plugin and its local Swift helpers are maintained in this repository under the [MIT license](../../LICENSE). Zukka, SwiftBar, Apple Calendar, and EventKit are separate products or services; their names identify integrations, not endorsement. No code from those projects is included here.
