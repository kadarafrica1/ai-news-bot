"""
image_handler.py
Strategy:
  1. RSS thumbnail from the article
  2. Fallback: Google Custom Search Images (free tier)
  3. Fallback: Download a free placeholder image (never crashes)
"""

import os
import re
import requests
from pathlib import Path

OUTPUT_DIR = Path("output/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX      = os.environ.get("GOOGLE_CX", "")

# Free placeholder image (no API key needed)
PLACEHOLDER_URL = "https://placehold.co/1200x630/1a1a2e/ffffff.jpg?text=AI+News+Bot"


def search_google_image(query: str, filename: str = "news_image.jpg") -> str | None:
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        print("[IMG] No Google keys — skipping.")
        return None
    try:
        print(f"[IMG] Searching Google Images: {query[:60]}")
        params = {
            "key":        GOOGLE_API_KEY,
            "cx":         GOOGLE_CX,
            "q":          query,
            "searchType": "image",
            "num":        1,
            "imgSize":    "LARGE",
            "imgType":    "photo",
            "safe":       "active",
        }
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params, timeout=10
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        return _download_image(items[0]["link"], filename)
    except Exception as e:
        print(f"[WARN] Google Images failed: {e}")
        return None


def download_rss_thumbnail(url: str, filename: str = "news_image.jpg") -> str | None:
    if not url:
        return None
    try:
        print("[IMG] Downloading RSS thumbnail …")
        return _download_image(url, filename)
    except Exception as e:
        print(f"[WARN] RSS thumbnail failed: {e}")
        return None


def download_placeholder(filename: str = "placeholder.jpg") -> str:
    """Always works — returns a simple placeholder image."""
    try:
        print("[IMG] Using placeholder image …")
        return _download_image(PLACEHOLDER_URL, filename)
    except Exception as e:
        print(f"[WARN] Placeholder download failed: {e}")
        # Last resort: create a tiny blank file so bot never crashes
        dest = OUTPUT_DIR / filename
        dest.write_bytes(b"")
        print(f"[IMG] Created empty fallback → {dest}")
        return str(dest)


def get_news_image(
    dalle_prompt: str,
    google_query: str,
    rss_thumbnail_url: str = "",
    filename: str = "news_image",
) -> str:
    safe_name = re.sub(r"[^\w]", "_", filename)[:40]

    # 1. RSS thumbnail (free, fastest)
    path = download_rss_thumbnail(rss_thumbnail_url, f"{safe_name}_rss.jpg")
    if path:
        return path

    # 2. Google Images (free tier, optional)
    path = search_google_image(google_query, f"{safe_name}_google.jpg")
    if path:
        return path

    # 3. Placeholder — never crashes the bot
    print("[IMG] All image sources failed — using placeholder.")
    return download_placeholder(f"{safe_name}_placeholder.jpg")


def _download_image(url: str, filename: str) -> str:
    dest = OUTPUT_DIR / filename
    resp = requests.get(
        url, timeout=20,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"[IMG] Saved → {dest}")
    return str(dest)


if __name__ == "__main__":
    path = get_news_image(
        dalle_prompt="",
        google_query="Trump press conference 2025",
        rss_thumbnail_url="",
    )
    print("Image path:", path)
