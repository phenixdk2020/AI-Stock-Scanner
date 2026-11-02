"""Offline tests af nyhedsscanneren (B-20)."""
import unittest
from datetime import date, datetime, timezone

from stockscanner import news
from stockscanner.news import NewsItem
from stockscanner.weekly_list import WeeklyRow, apply_news

FEED = """<?xml version="1.0"?><rss><channel>
<item><title>Novo hæver forventningerne - Børsen</title><link>https://n/1</link>
<pubDate>Mon, 02 Nov 2026 07:00:00 GMT</pubDate><source url="https://borsen.dk">Børsen</source></item>
<item><title>Novo hæver forventningerne - Finans</title><link>https://n/2</link>
<pubDate>Mon, 02 Nov 2026 06:00:00 GMT</pubDate><source url="https://finans.dk">Finans</source></item>
<item><title>Gammel nyhed - Børsen</title><link>https://n/3</link>
<pubDate>Mon, 12 Oct 2026 07:00:00 GMT</pubDate><source url="https://borsen.dk">Børsen</source></item>
</channel></rss>"""


def row(ticker, action="KØB-KANDIDAT"):
    return WeeklyRow(ticker, action, "køb 2026-10-30", None, None, None, 80.0, 50.0, 60.0, 70.0, 1.0,
                     "alle krav opfyldt", shares=10, stop=90.0)


class NewsTests(unittest.TestCase):
    def test_parse_feed_strips_source_dedupes_and_drops_old(self):
        items = news.parse_feed(FEED, now=datetime(2026, 11, 2, 12, tzinfo=timezone.utc))
        self.assertEqual([i.title for i in items], ["Novo hæver forventningerne"])
        self.assertEqual((items[0].source, items[0].published), ("Børsen", "2026-11-02"))

    def test_parse_ratings_validates(self):
        text = '{"vurderinger": [{"nr": 0, "retning": "Negativ", "betydning": 5, "begrundelse": "x"},' \
               ' {"nr": 9, "retning": "positiv"}, {"nr": 1, "retning": "måske"}]}'
        self.assertEqual(news.parse_ratings(text, 2), {0: ("negativ", 3, "x")})
        self.assertEqual(news.parse_ratings("ikke json", 2), {})

    def test_clean_name(self):
        self.assertEqual(news.clean_name("Novo Nordisk A/S B", "NOVO-B.CO"), "Novo Nordisk")
        self.assertEqual(news.clean_name("Microsoft Corporation", "MSFT"), "Microsoft")
        self.assertEqual(news.clean_name("", "X"), "X")

    def test_feed_language(self):
        self.assertEqual(news.feed_params("NOVO-B.CO")["hl"], "da")
        self.assertEqual(news.feed_params("MSFT")["hl"], "en-US")
        self.assertEqual(news.feed_params("SOBI.ST")["ceid"], "SE:sv")
        self.assertEqual(news.clean_name("SK Hynix R", "HY9H.F"), "SK Hynix")

    def test_summary_flags_recent_big_negative(self):
        items = [NewsItem("Afslag fra FDA", "Børsen", "u1", "2026-11-01", "negativ", 3, "x"),
                 NewsItem("Ny ordre", "Finans", "u2", "2026-11-02", "positiv", 2, "y")]
        text = news.summary(items, today=date(2026, 11, 2))
        self.assertTrue(text.startswith("nyheder: 1+ 1−"))
        self.assertIn("stor negativ nyhed (opvejet): Afslag fra FDA", text)   # lige mange gode og dårlige
        items.append(NewsItem("Retssag", "Børsen", "u3", "2026-11-02", "negativ", 2, "z"))
        self.assertIn("STOR NEGATIV NYHED: Afslag fra FDA", news.summary(items, today=date(2026, 11, 2)))
        self.assertNotIn("STOR", news.summary(items, today=date(2026, 11, 20)))
        self.assertIsNone(news.summary([]))

    def test_big_negative_news_blocks_buy(self):
        rows = apply_news([row("A"), row("B")], {"A": "nyheder: 0+ 1−; STOR NEGATIV NYHED: Afslag", "B": "nyheder: 1+ 0−"})
        by = {r.ticker: r for r in rows}
        self.assertEqual(by["A"].action, "hold øje")
        self.assertIsNone(by["A"].shares)
        self.assertIn("STOR NEGATIV NYHED", by["A"].reasons)
        self.assertEqual((by["B"].action, by["B"].news), ("KØB-KANDIDAT", "nyheder: 1+ 0−"))
        self.assertEqual(rows[0].ticker, "B")


if __name__ == "__main__":
    unittest.main()
