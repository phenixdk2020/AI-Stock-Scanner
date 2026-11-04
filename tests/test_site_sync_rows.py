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
        self.assertEqual([r["signal"] for r in payload["rows"]], ["Købskandidat", "Hold øje", "Salgssignal"])
        self.assertEqual(payload["rows"][1]["score"], 90)
        self.assertIs(type(payload["rows"][1]["score"]), int)

    def test_all_stocks_are_shown_without_guessing_a_score(self):
        rows = [row("NOSCORE", "hold øje", None), row("HY9H.F", "hold øje", 50), row("RSP", "hold øje", None)]
        payload = snapshot_from_rows(rows, {r.ticker: "2026-11-03" for r in rows})
        shown = {r["ticker"]: r for r in payload["rows"]}
        self.assertEqual(len(shown), 3)
        self.assertIsNone(shown["NOSCORE"]["score"])
        self.assertEqual(shown["HY9H.F"]["market"], "Andet")
        self.assertEqual(shown["NOSCORE"]["instrument_type"], "Aktie")
        self.assertEqual(shown["RSP"]["instrument_type"], "ETF")

    def test_no_date_means_no_row_and_row_limit(self):
        with self.assertRaises(ValueError):
            snapshot_from_rows([row("NODATE", "hold øje", 50)], {})
        many = [row(f"T{i}", "hold øje", 50) for i in range(60)]
        self.assertEqual(len(snapshot_from_rows(many, {r.ticker: "2026-11-03" for r in many})["rows"]), 50)


if __name__ == "__main__":
    unittest.main()
