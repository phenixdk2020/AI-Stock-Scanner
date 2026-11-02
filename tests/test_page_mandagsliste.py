"""Røgtest af Streamlit-siden Mandagsliste (Streamlit AppTest, ingen netværk)."""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "pages" / "1_Mandagsliste.py"


class PageTests(unittest.TestCase):
    def test_page_renders_without_exceptions(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("streamlit.testing ikke tilgængelig")
        app = AppTest.from_file(str(PAGE), default_timeout=30).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "🗓️ Mandagsliste")
        labels = [b.label for b in app.button]
        self.assertIn("Kør mandagslisten nu", labels)
        self.assertIn("Gem portefølje", labels)


if __name__ == "__main__":
    unittest.main()
