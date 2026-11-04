"""Aktiescanner-siden får rigtige data fra mandagslisten i stedet for demodata."""
import unittest
from types import SimpleNamespace

from stockscanner.site_sync import snapshot_from_rows


def row(ticker, action, score):
    return SimpleNamespace(ticker=ticker, action=action, mss_score=score)


class SnapshotFromRowsTests(unittest.TestCase):
    def test_real_rows_candidates_first(self):
        rows = [row("MSFT", "hold øje", 90.4), row("NOVO-B.CO", "KØB-KANDIDAT", 70), row("SAP.DE", "pil ned", 80)]
        dates = {r.ticker: "2026-11-03" for r in rows}
        payload = snapshot_from_rows(rows, dates)
        self.assertEqual(payload["mode"], "research")
        self.assertRegex(payload["generated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual([r["ticker"] for r in payload["rows"]], ["NOVO-B.CO", "MSFT", "SAP.DE"])
        self.assertEqual([r["signal"] for r in payload["rows"]], ["Interessant", "Hold øje", "Afvent"])
        self.assertEqual(payload["rows"][1]["score"], 90)
        self.assertIs(type(payload["rows"][1]["score"]), int)

    def test_no_guessing_and_row_limit(self):
        rows = [row("NOSCORE", "hold øje", None), row("NODATE", "hold øje", 50)]
        with self.assertRaises(ValueError):
            snapshot_from_rows(rows, {"NOSCORE": "2026-11-03"})
        many = [row(f"T{i}", "hold øje", 50) for i in range(60)]
        self.assertEqual(len(snapshot_from_rows(many, {r.ticker: "2026-11-03" for r in many})["rows"]), 50)


if __name__ == "__main__":
    unittest.main()
