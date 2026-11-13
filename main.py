"""Competitor Price Monitor."""
import argparse
import json
import re
import sqlite3
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

DROP_ALERT = 0.05


class Finder(HTMLParser):
    """Collects text inside the first element matching tag + class/id."""

    def __init__(self, selector):
        super().__init__()
        self.tag, _, self.cls = selector.partition(".")
        self.tag, _, self.id = self.tag.partition("#")
        self.depth, self.text = 0, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.depth:
            self.depth += 1
        elif self.text is None and tag == self.tag and (not self.cls or self.cls in (a.get("class") or "").split()) \
                and (not self.id or a.get("id") == self.id):
            self.depth, self.text = 1, ""

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text += data


def extract(html, selector):
    f = Finder(selector)
    f.feed(html)
    return (f.text or "").strip() or None


def to_price(text):
    if not text:
        return None
    m = re.search(r"(\d[\d,]*\.?\d*)", text.replace(" ", ""))
    return float(m.group(1).replace(",", "")) if m else None


def fetch(url):
    rp = urllib.robotparser.RobotFileParser(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
    rp.read()
    if not rp.can_fetch("PriceMonitorBot", url):
        raise PermissionError(f"robots.txt disallows {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "PriceMonitorBot/1.0 (contact: you@example.com)"})
    time.sleep(2)
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def run(watch, db, live, now):
    db.execute("CREATE TABLE IF NOT EXISTS prices (at TEXT, product TEXT, store TEXT, price REAL, in_stock INTEGER)")
    alerts = []
    for item in watch:
        for c in item["competitors"]:
            html = fetch(c["url"]) if live else Path(c["sample"]).read_text(encoding="utf-8")
            price = to_price(extract(html, c["price_selector"]))
            stock_txt = (extract(html, c["stock_selector"]) or "").lower()
            in_stock = 0 if "out of stock" in stock_txt or "sold out" in stock_txt else 1
            prev = db.execute("SELECT price FROM prices WHERE product=? AND store=? ORDER BY at DESC LIMIT 1",
                              (item["product"], c["store"])).fetchone()
            db.execute("INSERT INTO prices VALUES (?,?,?,?,?)", (now.isoformat(), item["product"], c["store"], price, in_stock))
            line = f"{item['product']:<26} {c['store']:<12} NGN {price:>9,.0f} {'in stock' if in_stock else 'OUT OF STOCK'}"
            if prev and prev[0] and price < prev[0] * (1 - DROP_ALERT):
                alerts.append(f"{c['store']} dropped {item['product']} from {prev[0]:,.0f} to {price:,.0f}")
            if in_stock and price < item["my_price"]:
                alerts.append(f"{c['store']} undercuts you on {item['product']}: {price:,.0f} vs your {item['my_price']:,}")
            print(line)
    db.commit()
    return alerts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true", help="fetch real pages instead of saved samples")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    watch = json.loads(Path("watchlist.json").read_text())
    Path("output").mkdir(exist_ok=True)
    db = sqlite3.connect("output/prices.db")
    if not a.live:  # seed yesterday's prices so the demo shows a drop
        db.execute("CREATE TABLE IF NOT EXISTS prices (at TEXT, product TEXT, store TEXT, price REAL, in_stock INTEGER)")
        db.execute("INSERT INTO prices VALUES (?,?,?,?,?)", ((datetime.now() - timedelta(days=1)).isoformat(),
                                                             "PowerPal 20K power bank", "GadgetHub", 29500, 1))
    alerts = run(watch, db, a.live, datetime.now())
    print("\nALERTS:" if alerts else "\nNo alerts today.")
    for x in alerts:
        print(f"  - {x}")


if __name__ == "__main__":
    main()
