"""Bear/Base/Bull for hele universet: cache, fejl og payload."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from stockscanner import playbook, universe_scenarios


class UniverseScenariosTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "s.json"

    def test_failing_stock_is_skipped_and_the_rest_continue(self):
        def channel(ticker):
            if ticker == "BAD":
                raise ValueError("ingen kursdata")
            return ticker

        with patch.object(universe_scenarios, "scenarios_entry", lambda c, cur, h: None if c == "NONE" else {"c": cur}):
            done = universe_scenarios.build(["OK", "BAD", "NONE"], {"OK": "DKK"}, channel, self.path, pause=0)
        self.assertEqual(done, {"OK": {"c": "DKK"}})
        self.assertEqual(universe_scenarios.load(self.path), done)

    def test_failed_run_keeps_last_weeks_numbers(self):
        self.path.write_text(json.dumps({"built": datetime.now(timezone.utc).isoformat(), "scenarios": {"A": {}}}),
                             encoding="utf-8")
        with patch.object(universe_scenarios, "scenarios_entry", lambda c, cur, h: None):
            universe_scenarios.build(["A"], {}, str, self.path, pause=0)
        self.assertEqual(universe_scenarios.load(self.path), {"A": {}})

    def test_old_or_broken_file_gives_nothing(self):
        self.assertEqual(universe_scenarios.load(self.path), {})
        self.path.write_text("ikke json", encoding="utf-8")
        self.assertEqual(universe_scenarios.load(self.path), {})
        old = datetime.now(timezone.utc) - timedelta(days=15)
        self.path.write_text(json.dumps({"built": old.isoformat(), "scenarios": {"A": {}}}), encoding="utf-8")
        self.assertEqual(universe_scenarios.load(self.path), {})


if __name__ == "__main__":
    unittest.main()
