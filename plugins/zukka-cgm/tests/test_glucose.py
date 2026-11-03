import contextlib
import importlib.machinery
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1] / "zukka-cgm.swiftbar/plugin.py"
loader = importlib.machinery.SourceFileLoader("glucose_plugin", str(PLUGIN))
spec = importlib.util.spec_from_loader(loader.name, loader)
glucose = importlib.util.module_from_spec(spec)
loader.exec_module(glucose)


class GlucoseTests(unittest.TestCase):
    def test_demo_is_labeled_and_does_not_read_private_data(self):
        output = io.StringIO()
        with mock.patch.object(glucose, "DEMO_MODE", True), \
             mock.patch.object(glucose, "get_readings", side_effect=AssertionError), \
             mock.patch.object(glucose, "record_history", side_effect=AssertionError), \
             mock.patch.object(glucose, "send_notification", side_effect=AssertionError), \
             mock.patch.object(glucose.sys, "argv", [str(PLUGIN)]), \
             contextlib.redirect_stdout(output):
            glucose.main()
        self.assertTrue(output.getvalue().startswith("DEMO · 128 →"))
        self.assertIn("Synthetic demo data", output.getvalue())

    def test_stale_reading_never_looks_current(self):
        output = io.StringIO()
        readings = [(16 * 60, "🟢 128 →", "128", "→")]
        with mock.patch.object(glucose, "DEMO_MODE", False), \
             mock.patch.object(glucose, "get_readings", return_value=readings), \
             mock.patch.object(glucose, "record_history", return_value=[]), \
             mock.patch.object(glucose, "maybe_alert", return_value=None), \
             mock.patch.object(glucose, "PAUSE_FILE", Path("/nonexistent-zukka-pause")), \
             mock.patch.object(glucose.sys, "argv", [str(PLUGIN)]), \
             contextlib.redirect_stdout(output):
            glucose.main()
        self.assertTrue(output.getvalue().startswith("Glucose stale · 16m"))
        self.assertIn("Calendar reading is stale", output.getvalue())

    def test_reader_restart_is_attempted_even_with_cached_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            reader = root / "Reader.app"
            reader.mkdir()
            cache = root / "cache.txt"
            cache.write_text("CALENDAR_ACCESS_DENIED\n")
            with mock.patch.object(glucose, "READER", reader), \
                 mock.patch.object(glucose, "CACHE_FILE", cache), \
                 mock.patch.object(glucose, "ensure_reader_running") as restart:
                with self.assertRaises(PermissionError):
                    glucose.get_readings()
                restart.assert_called_once()

    def test_walk_suggestion_is_optional_and_requires_a_fresh_reading(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = {**glucose.DEFAULT_ALERTS, "enabled": True}
            fresh = [(120, "🟢 130 ↑", "130", "↑")]
            with mock.patch.object(glucose, "LOCK_FILE", root / "lock"), \
                 mock.patch.object(glucose, "STATE_FILE", root / "state.json"), \
                 mock.patch.object(glucose, "send_notification", return_value=True) as send:
                glucose.maybe_alert(fresh, config)
                self.assertIn("consider a short walk", send.call_args.args[1].lower())
                send.reset_mock()
                glucose.maybe_alert([(11 * 60, "🟢 130 ↑", "130", "↑")], config)
                send.assert_not_called()

    def test_malformed_state_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            path.write_text("[]")
            self.assertEqual(glucose.load_json(path), {})


if __name__ == "__main__":
    unittest.main()
