"""
Terminal test - checks scraping works WITHOUT the browser.
Usage:  python test_scraper.py https://www.python.org
"""
import json
import sys

from scraper import ScrapeError, scrape_website

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.python.org"
print(f"Scraping {url} ...")
try:
    data = scrape_website(url)
except ScrapeError as e:
    print("Scrape error:", e)
    sys.exit(1)
data.pop("text_excerpt", None)
print(json.dumps(data, indent=2, ensure_ascii=False))
