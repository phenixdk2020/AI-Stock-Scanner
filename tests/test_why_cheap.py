import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import requests

from stockscanner import news, why_cheap
from stockscanner.analyst import AnalystInfo

GOOD = {"hvorfor_billig": "Omsætningen falder.", "risici": ["Svag vækst"], "vaerdifaelde": "middel",
        "datagrundlag": "omsætning"}
FACTS = {"omsaetning_aar_mio": [("2025-12-31", 1234), ("2024-12-31", 1500)], "gaeld_til_egenkapital": 0.45}
ITEMS = [news.NewsItem("Nedjustering af forventninger", "Kilde", "http://x", "2026-11-01", "negativ")]


import contextlib


@contextlib.contextmanager
def _no_queue(label):
    yield True


def fake_response(text):
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"response": text}
    return response


class Prompt(unittest.TestCase):
    def test_forbud_og_kun_givne_tal(self):
        prompt = why_cheap.build_prompt("ABC.CO", "Abc", FACTS, {"pe": 7.5}, AnalystInfo(trap="value trap: EPS"), ITEMS)
        for text in ("ALDRIG kursmål", "købs-/salgsråd", "ved ikke", "KUN tallene", "hoej"):
            self.assertIn(text, prompt)
        for text in ("1234", "1500", "0.45", "liste.pe: 7.5", "Nedjustering", "value trap"):
            self.assertIn(text, prompt)
        self.assertNotIn("9999", prompt)

    def test_manglende_data_giver_stadig_prompt(self):
        self.assertIn("Aktie: Abc (ABC.CO)", why_cheap.build_prompt("ABC.CO", "Abc", {}, None, None, []))


class Parse(unittest.TestCase):
    def test_gyldigt(self):
        self.assertEqual(why_cheap.parse_answer(json.dumps(GOOD)), GOOD)

    def test_kodeblok_og_think(self):
        text = "<think>hmm {x}</think>\n```json\n" + json.dumps(GOOD) + "\n```"
        self.assertEqual(why_cheap.parse_answer(text)["vaerdifaelde"], "middel")

    def test_ugyldigt(self):
        for text in ("", "ingen json", "[1,2]", '{"risici": []}', None):
            self.assertIsNone(why_cheap.parse_answer(text))

    def test_for_langt_og_ukendt_niveau(self):
        long = {"hvorfor_billig": "x" * 1000, "risici": ["y" * 500] * 6, "vaerdifaelde": "enorm",
                "datagrundlag": "z" * 1000}
        out = why_cheap.parse_answer(json.dumps(long))
        self.assertEqual(len(out["hvorfor_billig"]), why_cheap.MAX_WHY)
        self.assertEqual(len(out["risici"]), 3)
        self.assertTrue(all(len(r) <= why_cheap.MAX_RISK for r in out["risici"]))
        self.assertEqual(out["vaerdifaelde"], "ukendt")
        self.assertEqual(len(out["datagrundlag"]), why_cheap.MAX_BASIS)

    def test_opfundne_tal_fjernes(self):
        answer = dict(GOOD, hvorfor_billig="Omsætning 1234 mio. Kursmål 480 kr.")
        out = why_cheap._strip_invented(answer, "omsaetning 1234")
        self.assertEqual(out["hvorfor_billig"], "Omsætning 1234 mio.")
        self.assertIn("fjernet", out["datagrundlag"])


class Build(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patches = [mock.patch.object(why_cheap, "CACHE_FILE", Path(tmp.name) / "c.json"),
                   mock.patch.object(news, "ensure_ollama", return_value=True),
                   mock.patch.object(news, "gpu_turn", _no_queue),
                   mock.patch.object(why_cheap, "facts_for", return_value=FACTS)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.today = date(2026, 11, 5)

    def run_build(self, tickers, post, today=None):
        with mock.patch.object(why_cheap.requests, "post", post):
            return why_cheap.build(tickers, today=today or self.today, names={t: t for t in tickers})

    def test_cache_genbruges_i_7_dage(self):
        post = mock.Mock(return_value=fake_response(json.dumps(GOOD)))
        first = self.run_build(["A"], post)
        self.assertEqual(first["A"]["dato"], "2026-11-05")
        calls = post.call_count
        self.run_build(["A"], post, today=self.today + timedelta(days=6))
        self.assertEqual(post.call_count, calls)  # intet nyt kald
        self.run_build(["A"], post, today=self.today + timedelta(days=7))
        self.assertGreater(post.call_count, calls)  # forældet

    def test_max_per_run(self):
        post = mock.Mock(return_value=fake_response(json.dumps(GOOD)))
        tickers = [f"T{i}" for i in range(40)]
        out = self.run_build(tickers, post)
        self.assertEqual(len(out), why_cheap.MAX_PER_RUN)
        self.assertEqual(list(out), tickers[:why_cheap.MAX_PER_RUN])

    def test_ollama_fejl_stopper_ikke(self):
        self.run_build(["A"], mock.Mock(return_value=fake_response(json.dumps(GOOD))))
        failing = mock.Mock(side_effect=requests.ConnectionError("nede"))
        out = self.run_build(["A", "B"], failing, today=self.today + timedelta(days=30))
        self.assertEqual(list(out), ["A"])  # forældet cache gives stadig; B har intet

    def test_ollama_nede(self):
        with mock.patch.object(news, "ensure_ollama", return_value=False):
            self.assertEqual(self.run_build(["A"], mock.Mock()), {})


if __name__ == "__main__":
    unittest.main()
