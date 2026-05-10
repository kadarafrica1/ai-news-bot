"""
image_handler.py
Strategy:
  1. Try DALL-E 3 first (AI-generated editorial image).
  2. If DALL-E fails / is unavailable, fall back to Google Custom Search Images.
  3. If both fail, use the thumbnail URL from the RSS feed itself.
Returns a local file path ready for uploading to social platforms.
"""

import os
import re
import requests
from pathlib import Path
from openai import OpenAI

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

OUTPUT_DIR = Path("output/images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CX      = os.environ.get("GOOGLE_CX", "")       # Custom Search Engine ID


# ── DALL-E 3 ─────────────────────────────────────────────────────────────────

def generate_dalle_image(prompt: str, filename: str = "news_image.png") -> str | None:
    """Generate an image with DALL-E 3 and save it locally."""
    try:
        print("[IMG] Generating DALL-E image …")
        # Prepend a style directive so results look like editorial photography
        styled_prompt = (
            "Editorial news photography style, realistic, high quality, "
            "professional photojournalism: " + prompt
        )
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=styled_prompt[:4000],
            size="1792x1024",        # landscape — good for all platforms
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        return _download_image(image_url, filename)
    except Exception as e:
        print(f"[WARN] DALL-E failed: {e}")
        return None


# ── Google Custom Search Images ───────────────────────────────────────────────

def search_google_image(query: str, filename: str = "news_image.jpg") -> str | None:
    """Search Google Images for the best matching photo."""
    if not GOOGLE_API_KEY or not GOOGLE_CX:
        print("[WARN] Google API keys not configured, skipping Google Images.")
        return None
    try:
        print(f"[IMG] Searching Google Images for: {query[:60]}")
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
        resp = requests.get("https://www.googleapis.com/customsearch/v1", params=params, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        image_url = items[0]["link"]
        return _download_image(image_url, filename)
    except Exception as e:
        print(f"[WARN] Google Images failed: {e}")
        return None


# ── RSS thumbnail fallback ────────────────────────────────────────────────────

def download_rss_thumbnail(url: str, filename: str = "news_image.jpg") -> str | None:
    """Download the thumbnail that came with the RSS entry."""
    if not url:
        return None
    try:
        print("[IMG] Using RSS thumbnail …")
        return _download_image(url, filename)
    except Exception as e:
        print(f"[WARN] RSS thumbnail download failed: {e}")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def get_news_image(
    dalle_prompt: str,
    google_query: str,
    rss_thumbnail_url: str = "",
    filename: str = "news_image",
) -> str:
    """
    Try DALL-E → Google Images → RSS thumbnail.
    Returns local path to saved image, or raises RuntimeError if all fail.
    """
    safe_name = re.sub(r"[^\w]", "_", filename)[:40]

    # 1. DALL-E
    path = generate_dalle_image(dalle_prompt, f"{safe_name}_dalle.png")
    if path:
        return path

    # 2. Google Images
    path = search_google_image(google_query, f"{safe_name}_google.jpg")
    if path:
        return path

    # 3. RSS thumbnail
    path = download_rss_thumbnail(rss_thumbnail_url, f"{safe_name}_rss.jpg")
    if path:
        return path

    raise RuntimeError("All image sources failed — cannot produce an image.")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _download_image(url: str, filename: str) -> str:
    dest = OUTPUT_DIR / filename
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    print(f"[IMG] Saved → {dest}")
    return str(dest)


if __name__ == "__main__":
    path = get_news_image(
        dalle_prompt="Donald Trump speaking at a press conference, White House background, editorial style",
        google_query="Trump press conference 2025",
    )
    print("Image path:", path)
