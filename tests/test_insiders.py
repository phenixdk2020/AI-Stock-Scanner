import unittest
from datetime import date

from stockscanner import insiders

XML = """<?xml version="1.0"?>
<ownershipDocument xmlns="http://x">
<reportingOwner><reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>true</isOfficer></reportingOwnerRelationship></reportingOwner>
<reportingOwner><reportingOwnerId><rptOwnerName>Doe Jane</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isTenPercentOwner>1</isTenPercentOwner></reportingOwnerRelationship></reportingOwner>
<reportingOwner><reportingOwnerId><rptOwnerName>ROE RICK</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isDirector>0</isDirector></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable>
{tx}
</nonDerivativeTable></ownershipDocument>"""


def tx(code, day, shares, price):
    return (f"<nonDerivativeTransaction><transactionDate><value>{day}</value></transactionDate>"
            f"<transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>"
            f"<transactionAmounts><transactionShares><value>{shares}</value></transactionShares>"
            f"<transactionPricePerShare><value>{price}</value></transactionPricePerShare></transactionAmounts>"
            f"</nonDerivativeTransaction>")


TODAY = date(2026, 11, 5)


class InsiderTests(unittest.TestCase):
    def test_parse_codes_and_owners(self):
        body = tx("P", "2026-10-20", 100, 10) + tx("S", "2026-10-21", 50, 12) + tx("A", "2026-10-22", 9, 0) + tx("M", "2026-10-22", 9, 1)
        rows = insiders.parse_form4(XML.replace("{tx}", body))
        self.assertEqual([r["code"] for r in rows], ["P", "S", "A", "M"])
        self.assertEqual(rows[0]["owners"], ["DOE JANE", "ROE RICK"])
        self.assertEqual(rows[0]["roles"], ["officer", "director", "10%-ejer"])
        self.assertEqual(rows[0]["value"], 1000.0)

    def test_summarize_ignores_other_codes_and_old(self):
        body = (tx("P", "2026-10-20", 100, 10) + tx("P", "2026-09-01", 10, 10) + tx("P", "2025-01-01", 999, 10)
                + tx("S", "2026-10-21", 50, 12) + tx("A", "2026-10-22", 9, 5) + tx("M", "2026-10-22", 9, 5))
        s = insiders.summarize(insiders.parse_form4(XML.replace("{tx}", body)), TODAY)
        self.assertEqual(s, {"buyers": 2, "buys": 2, "value_usd": 1100.0, "sells": 1,
                             "last_buy": "2026-10-20", "days": 90})

    def test_empty_and_broken(self):
        self.assertEqual(insiders.parse_form4("ikke xml"), [])
        s = insiders.summarize([], TODAY)
        self.assertEqual((s["buys"], s["last_buy"]), (0, None))

    def test_raw_doc(self):
        self.assertEqual(insiders._raw_doc("xslF345X05/form4.xml"), "form4.xml")
        self.assertEqual(insiders._raw_doc("form4.xml"), "form4.xml")

    def test_foreign_suffix_no_network(self):
        orig = insiders.cik_for
        insiders.cik_for = lambda t: self.fail("skal ikke slå CIK op")
        try:
            self.assertIsNone(insiders.fetch("NOVO-B.CO", TODAY))
            self.assertIsNone(insiders.fetch("VOD.L", TODAY))
        finally:
            insiders.cik_for = orig

    def test_build_never_raises(self):
        orig = insiders.fetch

        def fake(t, today, days=90):
            if t == "BAD":
                raise RuntimeError("x")
            return None if t == "NONE" else {"buys": 1}
        insiders.fetch = fake
        try:
            self.assertEqual(insiders.build(["BAD", "NONE", "OK"], TODAY), {"OK": {"buys": 1}})
            self.assertEqual(insiders.build(None, TODAY), {})
        finally:
            insiders.fetch = orig


class YahooFrameTests(unittest.TestCase):
    def test_only_real_market_buys_count(self):
        import pandas as pd

        frame = pd.DataFrame([
            {"Start Date": "2026-10-01", "Insider": "A", "Text": "Purchase at price 10 per share.", "Value": 50000},
            {"Start Date": "2026-10-02", "Insider": "A", "Text": "Purchase at price 11 per share.", "Value": 20000},
            {"Start Date": "2026-10-03", "Insider": "B", "Text": "Purchase at price 11 per share.", "Value": 602},
            {"Start Date": "2026-10-04", "Insider": "C", "Text": "Sale at price 12 per share.", "Value": 90000},
            {"Start Date": "2026-10-05", "Insider": "D", "Text": "Stock Award(Grant)", "Value": float("nan")},
            {"Start Date": "2025-01-01", "Insider": "E", "Text": "Purchase at price 9 per share.", "Value": 80000},
        ])
        result = insiders.from_frame(frame, date(2026, 11, 5))
        self.assertEqual((result["buyers"], result["buys"], result["sells"]), (1, 2, 1))
        self.assertEqual(result["value_usd"], 70000)
        self.assertEqual(result["last_buy"], "2026-10-02")


if __name__ == "__main__":
    unittest.main()
