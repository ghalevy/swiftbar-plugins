# SwiftBar plugins

Small, independent menu bar tools for [SwiftBar](https://github.com/swiftbar/SwiftBar). Each plugin lives in its own directory with its setup instructions, source, and tests. Install only the ones you want.

## Plugins

| Plugin | What it does |
| --- | --- |
| [Zukka CGM Calendar](plugins/zukka-cgm/README.md) | Displays recent glucose values, trend, reading age, local history charts, and optional notifications from Zukka Calendar Share. |

Zukka CGM Calendar is a convenience display. It is not a substitute for your primary CGM app, official monitoring equipment, safety alerts, or medical decisions.

## Install a plugin

Read the plugin's own README for requirements and setup. Keep its directory together: a plugin may depend on adjacent helper files. Zukka is a [SwiftBar packaged plugin](https://github.com/swiftbar/SwiftBar/blob/main/README-PACKAGED-PLUGINS.md); copy its `.swiftbar` package as a unit.

## Contribute

Open a GitHub issue with the plugin name, macOS and SwiftBar versions, the expected behavior, and a redacted error description. Never post glucose readings, calendar titles, credentials, or private logs. Pull requests should include focused tests when behavior changes.

For a new plugin, add `plugins/<short-name>/` with its own README, entry point or SwiftBar package, required helper sources, and a small test suite. Keep runtime data and local configuration out of Git. Version each plugin in its SwiftBar metadata and document any external dependencies in that plugin's README. Add screenshots only with synthetic or redacted data. Shared code belongs in `scripts/` only when more than one real plugin needs it.

## License

MIT. See [LICENSE](LICENSE). Each plugin's documentation notes its third-party services and permissions.
