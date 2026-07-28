import os
import re
import urllib.parse
from pathlib import Path
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRAPERAPI_KEY = os.getenv("SCRAPERAPI_KEY", "").strip()
MOVIE_URL = os.getenv("MOVIE_URL", "https://in.bookmyshow.com/movies/chennai/spiderman-brand-new-day/buytickets/ET00502600/20260802")
VENUE_CODES = [c.strip() for c in os.getenv("VENUE_CODES", "PCAN,PVPZ,PABC").split(",") if c.strip()]
REQUESTED_DATE = os.getenv("REQUESTED_DATE", "20260802")

def detect_open_venues(page_text, codes, date):
    open_venues = []
    for code in codes:
        pattern = re.compile(
            r'https?://[^\s"\'<>]+/cinemas/[^\s"\'<>]+/buytickets/' + re.escape(code) + r'/' + re.escape(date),
            re.IGNORECASE
        )
        match = pattern.search(page_text)
        if match:
            open_venues.append({"code": code.upper(), "url": match.group(0)})
        elif f"/{code.lower()}/{date}" in page_text.lower():
            open_venues.append({"code": code.upper(), "url": MOVIE_URL})
    return open_venues

def run_test():
    print("🔍 Fetching page via ScraperAPI...")
    api_url = "https://api.scraperapi.com/?" + urllib.parse.urlencode(
        {"api_key": SCRAPERAPI_KEY, "country_code": "in", "url": MOVIE_URL}
    )
    resp = requests.get(api_url, timeout=90)
    html = resp.text

    venues = detect_open_venues(html, VENUE_CODES, REQUESTED_DATE)
    print(f"\n✅ Open Venues Found: {len(venues)}")
    
    for v in venues:
        print(f"\n📍 Venue Code: {v['code']}")
        print(f"🔗 Direct Booking Link: {v['url']}")

    if venues:
        venue_links = "\n".join([f"• {v['code']}: {v['url']}" for v in venues])
        sample_msg = (
            f"🎬 Booking OPENED!\n\n"
            f"Movie: Spider-Man: Brand New Day\n"
            f"Date: 02-08-2026\n\n"
            f"Direct Theatre Links:\n"
            f"{venue_links}"
        )
        print("\n--- SAMPLE TELEGRAM / WHATSAPP MESSAGE ---")
        print(sample_msg)

if __name__ == "__main__":
    run_test()