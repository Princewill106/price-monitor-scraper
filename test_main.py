import unittest
from pathlib import Path

import main


class ScraperTests(unittest.TestCase):
    def test_extract(self):
        html = Path("sample_page_gadgethub.html").read_text()
        self.assertEqual(main.to_price(main.extract(html, "span.price")), 25900)
        t = Path("sample_page_techmart.html").read_text()
        self.assertEqual(main.to_price(main.extract(t, "div#product-price")), 28500)

    def test_class_matching(self):
        html = '<span class="price-old">1</span><span class="price">2</span>'
        self.assertEqual(main.extract(html, "span.price"), "2")


if __name__ == "__main__":
    unittest.main()
