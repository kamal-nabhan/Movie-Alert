#!/usr/bin/env python3
"""
Ticket-booking watcher.

Polls a BookMyShow / District showtimes page and sends a Telegram + WhatsApp
message the moment a given theatre appears with booking open.
"""

import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", ROOT / "config.json"))
STATE_PATH = Path(os.environ.get("STATE_PATH", ROOT / "state.json"))

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
}


def load_json(path, default=None):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_config():
    cfg = load_json(CONFIG_PATH, default={}) or {}

    env_map = {
        "TARGET_URL": "target_url",
        "THEATRE": "theatre",
        "MOVIE": "movie",
        "REQUESTED_DATE": "requested_date",
        "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
        "TELEGRAM_CHAT_ID": "telegram_chat_id",
        "WHATSAPP_PHONE": "whatsapp_phone",
        "WHATSAPP_APIKEY": "whatsapp_apikey",
    }
    for env_key, cfg_key in env_map.items():
        if os.environ.get(env_key):
            cfg[cfg_key] = os.environ[env_key]

    if cfg.get("url_template") and cfg.get("requested_date"):
        cfg["target_url"] = cfg["url_template"].format(date=cfg["requested_date"])

    required = ["target_url", "telegram_bot_token", "telegram_chat_id"]
    detector = cfg.get("detector")
    if detector in ("bms_date", "venue_date"):
        required.append("requested_date")

    if detector == "venue_date" and not (cfg.get("venue_code") or cfg.get("venue_codes")):
        sys.exit("venue_date detector needs 'venue_code' or 'venue_codes'")

    missing = [k for k in required if not cfg.get(k)]
    if missing:
        sys.exit(f"Missing required config: {', '.join(missing)}")
    return cfg


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
        timeout=30,
    )
    resp.raise_for_status()


def send_whatsapp_group(text):
    """Sends WhatsApp message to a group via Green-API."""
    id_instance = os.environ.get("GREEN_API_ID")
    api_token = os.environ.get("GREEN_API_TOKEN")
    group_id = os.environ.get("WHATSAPP_GROUP_ID")
    
    if not id_instance or not api_token or not group_id:
        return
        
    url = f"https://api.green-api.com/waInstance{id_instance}/sendMessage/{api_token}"
    
    payload = {
        "chatId": group_id,
        "message": text
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        print("[WhatsApp] Group notification sent successfully")
    except requests.RequestException as exc:
        print(f"[WhatsApp] Group notification failed: {exc}")


def fetch(cfg):
    headers = dict(DEFAULT_HEADERS)
    headers.update(cfg.get("headers", {}))

    scraper_key = os.environ.get("SCRAPERAPI_KEY")
    if scraper_key:
        api_url = "https://api.scraperapi.com/?" + urllib.parse.urlencode(
            {"api_key": scraper_key, "country_code": "in", "url": cfg["target_url"]}
        )
        resp = requests.get(api_url, timeout=90)
        resp.raise_for_status()
        return resp.text

    proxy = os.environ.get("PROXY_URL")
    proxies = {"http": proxy, "https": proxy} if proxy else None

    session = requests.Session()
    session.headers.update(headers)
    resp = session.get(cfg["target_url"], timeout=30, proxies=proxies)
    resp.raise_for_status()
    return resp.text


def detect_open_venues(page_text, cfg):
    """
    Scans HTML for specific venue codes and extracts their direct booking links.
    Returns a list of dicts: [{'code': 'PABC', 'url': 'https://in.bookmyshow.com/cinemas/.../PABC/20260802'}]
    """
    date = cfg["requested_date"]
    codes = cfg.get("venue_codes") or [cfg["venue_code"]]
    open_venues = []

    for code in codes:
        # Regex to find direct theatre booking links embedded in BMS JSON/HTML
        pattern = re.compile(
            r'https?://[^\s"\'<>]+/cinemas/[^\s"\'<>]+/buytickets/' + re.escape(code) + r'/' + re.escape(date),
            re.IGNORECASE
        )
        match = pattern.search(page_text)
        
        if match:
            open_venues.append({"code": code.upper(), "url": match.group(0)})
        elif f"/{code.lower()}/{date}" in page_text.lower():
            open_venues.append({"code": code.upper(), "url": cfg["target_url"]})

    return open_venues


def main():
    cfg = load_config()
    state = load_json(STATE_PATH, default={"available": False}) or {"available": False}

    label = f"{cfg.get('movie', 'Movie')} @ {cfg.get('requested_date', 'target')}"

    try:
        page = fetch(cfg)
    except requests.RequestException as exc:
        print(f"[{label}] fetch failed: {exc}")
        return 0

    open_venues = detect_open_venues(page, cfg)
    available = len(open_venues) > 0

    print(f"[{label}] available={available} (open venues: {[v['code'] for v in open_venues]})")

    if available and not state.get("available"):
        rd = cfg["requested_date"]
        pretty_date = f"{rd[6:8]}-{rd[4:6]}-{rd[0:4]}"

        # Construct specific message with direct theatre links
        venue_links = "\n".join([f"• {v['code']}: {v['url']}" for v in open_venues])
        
        msg = (
            f"🎬 Booking OPENED!\n\n"
            f"Movie: {cfg.get('movie', 'Movie')}\n"
            f"Date: {pretty_date}\n\n"
            f"Direct Theatre Links:\n"
            f"{venue_links}"
        )

        # 1. Send Telegram Notification
        send_telegram(cfg["telegram_bot_token"], cfg["telegram_chat_id"], msg)
        print(f"[{label}] Telegram notification sent")

        # 2. Send WhatsApp Group Notification
        send_whatsapp_group(msg)

    # Persist state
    if available != state.get("available"):
        state["available"] = available
        state["checked_at"] = int(time.time())
        save_json(STATE_PATH, state)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())