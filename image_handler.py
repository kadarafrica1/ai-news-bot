"""
image_handler.py

Image strategy (in order of priority):
1. Open Graph / twitter:image from the article URL  ← NEW — best quality
2. RSS thumbnail embedded in the feed
3. Google Custom Search Images (optional, needs API key)
4. Plain coloured JPEG fallback  (never shows "AI News Bot" text)
"""

import os
import re
import requests
from pathlib import Path

OUTPUT_DIR = Path("output/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX      = os.environ.get("GOOGLE_CX", "")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"}


# ── 1. Open Graph image from article URL ─────────────────────────────────────
def fetch_og_image(article_url: str, filename: str = "og_image.jpg") -> str | None:
    """
    Fetch the og:image or twitter:image meta tag from the article page.
    This gives the actual editorial photo used by the news site.
    """
    if not article_url:
        return None
    try:
        print(f"[IMG] Fetching OG image from article …")
        resp = requests.get(article_url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        html = resp.text

        for tag in ["og:image", "twitter:image"]:
            # property/name before content
            pattern = (
                rf'<meta[^>]+(?:property|name)=["\'{tag}"\'][^>]+'
                rf'content=["\'](https?://[^"\']+)["\']'
            )
            match = re.search(pattern, html, re.IGNORECASE)
            if not match:
                # content before property/name
                pattern = (
                    rf'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+'
                    rf'(?:property|name)=["\'{tag}"\']'
                )
                match = re.search(pattern, html, re.IGNORECASE)
            if match:
                og_url = match.group(1)
                print(f"[IMG] OG image found: {og_url[:80]}")
                return _download_image(og_url, filename)

        print("[IMG] No OG image meta tag found.")
        return None
    except Exception as e:
        print(f"[WARN] OG image fetch failed: {e}")
        return None


# ── 2. RSS thumbnail ──────────────────────────────────────────────────────────
def download_rss_thumbnail(url: str, filename: str = "rss_thumb.jpg") -> str | None:
    if not url:
        return None
    try:
        print("[IMG] Downloading RSS thumbnail …")
        return _download_image(url, filename)
    except Exception as e:
        print(f"[WARN] RSS thumbnail failed: {e}")
        return None


# ── 3. Google Custom Search Images ───────────────────────────────────────────
def search_google_image(query: str, filename: str = "google_image.jpg") -> str | None:
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


# ── 4. Plain colour fallback (no text watermark) ─────────────────────────────
def download_placeholder(filename: str = "placeholder.jpg") -> str:
    """
    Creates a solid dark-blue 1200×630 JPEG.
    No "AI News Bot" text — the article link card will show the title anyway.
    """
    try:
        # Use a plain colour swatch — no text at all
        plain_url = "https://placehold.co/1200x630/1a1a2e/1a1a2e.jpg"
        print("[IMG] Using plain colour placeholder (no text) …")
        return _download_image(plain_url, filename)
    except Exception as e:
        print(f"[WARN] Placeholder download failed: {e}")
        dest = OUTPUT_DIR / filename
        # Write a minimal 1×1 white JPEG so the bot never crashes
        dest.write_bytes(
            bytes.fromhex(
                "ffd8ffe000104a46494600010100000100010000"
                "ffdb004300080606070605080707070909080a0c"
                "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20"
                "242e2720222c231c1c2837292c30313434341f27"
                "39383240303334320ffd9"
            )
        )
        return str(dest)


# ── Main entry point ──────────────────────────────────────────────────────────
def get_news_image(
    dalle_prompt: str,
    google_query: str,
    rss_thumbnail_url: str = "",
    article_url: str = "",          # ← NEW parameter
    filename: str = "news_image",
) -> str:
    safe_name = re.sub(r"[^\w]", "_", filename)[:40]

    # 1. OG image from the article page (best quality, always relevant)
    path = fetch_og_image(article_url, f"{safe_name}_og.jpg")
    if path:
        return path

    # 2. RSS thumbnail
    path = download_rss_thumbnail(rss_thumbnail_url, f"{safe_name}_rss.jpg")
    if path:
        return path

    # 3. Google Images
    path = search_google_image(google_query, f"{safe_name}_google.jpg")
    if path:
        return path

    # 4. Plain colour placeholder — never crashes
    print("[IMG] All image sources failed — using plain placeholder.")
    return download_placeholder(f"{safe_name}_placeholder.jpg")


# ── Helpers ───────────────────────────────────────────────────────────────────
def _download_image(url: str, filename: str) -> str:
    dest = OUTPUT_DIR / filename
    resp = requests.get(url, timeout=20, headers=HEADERS)
    resp.raise_for_status()
    if len(resp.content) < 500:
        raise ValueError("Downloaded file too small — likely not an image.")
    dest.write_bytes(resp.content)
    print(f"[IMG] Saved → {dest}")
    return str(dest)


if __name__ == "__main__":
    path = get_news_image(
        dalle_prompt="",
        google_query="Trump Iran war 2026",
        rss_thumbnail_url="",
        article_url="https://www.aljazeera.com/news/2026/6/4/us-house-votes-to-end-trumps-iran-war-does-it-matter",
    )
    print("Image path:", path)
