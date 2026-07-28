import os
import re
import sys
import urllib.parse
from pathlib import Path

import requests

# Try using python-dotenv; fall back to custom lightweight parser if not installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# Configuration pulled from .env with fallback defaults
SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "").strip()
MOVIE_URL = os.getenv(
    "MOVIE_URL",
    "https://in.bookmyshow.com/movies/chennai/spiderman-brand-new-day/buytickets/ET00447840/20260802",
)
VENUE_CODES_RAW = os.getenv("VENUE_CODES", "PCAN,PVPZ,PABC")
VENUE_CODES = [c.strip() for c in VENUE_CODES_RAW.split(",") if c.strip()]
REQUESTED_DATE = os.getenv("REQUESTED_DATE", "20260802")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
}


def run_debug():
    print("=" * 60)
    print("⚙️  ENVIRONMENT CONFIGURATION")
    print("=" * 60)
    print(f"ScraperAPI Key : {'Set (' + SCRAPERAPI_KEY[:6] + '...)' if SCRAPERAPI_KEY else '❌ Missing'}")
    print(f"Movie URL      : {MOVIE_URL}")
    print(f"Venue Codes    : {VENUE_CODES}")
    print(f"Requested Date : {REQUESTED_DATE}\n")

    print("🔍 Fetching page via ScraperAPI...")

    if SCRAPERAPI_KEY and "your_" not in SCRAPERAPI_KEY.lower():
        api_url = "https://api.scraperapi.com/?" + urllib.parse.urlencode(
            {"api_key": SCRAPERAPI_KEY, "country_code": "in", "url": MOVIE_URL}
        )
        try:
            resp = requests.get(api_url, timeout=90)
        except requests.RequestException as e:
            sys.exit(f"❌ ScraperAPI Request Failed: {e}")
    else:
        print("⚠️ No valid ScraperAPI key found in .env! Making direct request...")
        try:
            resp = requests.get(MOVIE_URL, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            sys.exit(f"❌ Direct Request Failed: {e}")

    print(f"Status Code    : {resp.status_code}")
    html = resp.text
    print(f"Page size      : {len(html)} characters\n")

    print("=" * 60)
    print("TEST 1: Exact Pattern Matching")
    print("=" * 60)

    for code in VENUE_CODES:
        pattern_upper = f"/{code}/{REQUESTED_DATE}"
        pattern_lower = f"/{code.lower()}/{REQUESTED_DATE}"

        match_upper = pattern_upper in html
        match_lower = pattern_lower in html

        print(f"Venue Code: {code}")
        print(f"  ├── Match '{pattern_upper}': {match_upper}")
        print(f"  └── Match '{pattern_lower}': {match_lower}")

    print("\n" + "=" * 60)
    print("TEST 2: Case-Insensitive Raw Occurrences & HTML Snippets")
    print("=" * 60)

    for code in VENUE_CODES:
        matches = [m.start() for m in re.finditer(re.escape(code), html, re.IGNORECASE)]
        print(f"\n📍 Code '{code}' found {len(matches)} time(s) in HTML:")

        if not matches:
            print("   (No mentions found on page)")

        for idx, pos in enumerate(matches[:3]):  # Show up to 3 snippets
            start = max(0, pos - 70)
            end = min(len(html), pos + 90)
            snippet = html[start:end].replace("\n", " ")
            print(f"   [{idx + 1}] ...{snippet}...")

    print("\n" + "=" * 60)
    print("TEST 3: Date Token Check")
    print("=" * 60)
    date_count = len(re.findall(REQUESTED_DATE, html))
    print(f"Date string '{REQUESTED_DATE}' appeared {date_count} time(s) on the page.\n")


if __name__ == "__main__":
    run_debug()