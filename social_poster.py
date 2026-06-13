"""
social_poster.py
Posts the AI-generated news content to:
• Twitter / X       (via Tweepy v4)
• Facebook Page     (via Graph API)
• Bluesky           (via atproto — with proper article image card)
• Website           (via GitHub Pages JSON feed)
"""

import os
import json
import time
import requests
import tweepy
from datetime import datetime, timezone
from pathlib import Path

# ── atproto for Bluesky ───────────────────────────────────────────────────────
try:
    from atproto import Client as BskyClient
    ATPROTO_AVAILABLE = True
except ImportError:
    ATPROTO_AVAILABLE = False
    print("[BLUESKY] atproto library not installed — skipping Bluesky.")

# ── Credentials from environment variables ────────────────────────────────────
TW_API_KEY          = os.environ.get("TWITTER_API_KEY", "")
TW_API_SECRET       = os.environ.get("TWITTER_API_SECRET", "")
TW_ACCESS_TOKEN     = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TW_ACCESS_SECRET    = os.environ.get("TWITTER_ACCESS_SECRET", "")

FB_PAGE_ID          = os.environ.get("FACEBOOK_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")

BLUESKY_HANDLE      = os.environ.get("BLUESKY_HANDLE", "")        # e.g. hollynews.bsky.social
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")  # App password from bsky.app settings

WEBSITE_FEED_PATH   = Path("output/website/feed.json")


# ── Twitter / X ───────────────────────────────────────────────────────────────
def post_twitter(caption: str, image_path: str) -> dict:
    print("[TWITTER] Posting …")
    if not all([TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET]):
        print("[TWITTER] Skipped — credentials missing.")
        return {"status": "skipped", "reason": "credentials missing"}
    try:
        auth   = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media  = api_v1.media_upload(filename=image_path)
        client = tweepy.Client(
            consumer_key=TW_API_KEY,
            consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN,
            access_token_secret=TW_ACCESS_SECRET,
        )
        tweet    = client.create_tweet(text=caption[:280], media_ids=[media.media_id])
        tweet_id = tweet.data["id"]
        print(f"[TWITTER] ✓ Tweet ID: {tweet_id}")
        return {"status": "success", "tweet_id": tweet_id,
                "url": f"https://twitter.com/i/web/status/{tweet_id}"}
    except Exception as e:
        print(f"[TWITTER] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Facebook Page ─────────────────────────────────────────────────────────────
def post_facebook(caption: str, image_path: str) -> dict:
    print("[FACEBOOK] Posting …")
    if not all([FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN]):
        print("[FACEBOOK] Skipped — credentials missing.")
        return {"status": "skipped", "reason": "credentials missing"}
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
        with open(image_path, "rb") as f:
            resp = requests.post(
                url,
                data={"caption": caption, "access_token": FB_PAGE_ACCESS_TOKEN},
                files={"source": f},
                timeout=30,
            )
        resp.raise_for_status()
        post_id = resp.json().get("post_id") or resp.json().get("id")
        print(f"[FACEBOOK] ✓ Post ID: {post_id}")
        return {"status": "success", "post_id": post_id}
    except Exception as e:
        print(f"[FACEBOOK] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Bluesky ───────────────────────────────────────────────────────────────────
def _fetch_og_image_url(article_url: str) -> str | None:
    """Fetch the Open Graph image URL from the article's HTML <meta> tags."""
    try:
        resp = requests.get(
            article_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        )
        resp.raise_for_status()
        html = resp.text

        # Try og:image first
        for tag in ['og:image', 'twitter:image']:
            import re
            pattern = rf'<meta[^>]+(?:property|name)=["\']{tag}["\'][^>]+content=["\'](https?://[^"\']+)["\']'
            match = re.search(pattern, html, re.IGNORECASE)
            if not match:
                # Try reversed attribute order: content first, then property
                pattern = rf'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+(?:property|name)=["\']{tag}["\']'
                match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        print(f"[BLUESKY] OG image fetch failed: {e}")
        return None


def _upload_image_blob(client, image_path: str):
    """Upload image to Bluesky and return blob reference."""
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    # Detect mime type
    mime = "image/jpeg"
    if image_path.lower().endswith(".png"):
        mime = "image/png"
    elif image_path.lower().endswith(".webp"):
        mime = "image/webp"

    resp = client.upload_blob(img_bytes)
    return resp.blob


def post_bluesky(
    caption: str,
    image_path: str,
    article_url: str,
    article_title: str,
    article_description: str = "",
) -> dict:
    """
    Post to Bluesky with a proper external link card showing the
    article image — NOT a placeholder.

    Strategy for the card thumbnail:
      1. Fetch the article's OG/twitter image from its HTML
      2. Download that image and upload as Bluesky blob
      3. Fall back to the local image_path if OG fetch fails
    """
    print("[BLUESKY] Posting …")

    if not ATPROTO_AVAILABLE:
        return {"status": "skipped", "reason": "atproto not installed"}
    if not all([BLUESKY_HANDLE, BLUESKY_APP_PASSWORD]):
        print("[BLUESKY] Skipped — BLUESKY_HANDLE or BLUESKY_APP_PASSWORD missing.")
        return {"status": "skipped", "reason": "credentials missing"}

    try:
        client = BskyClient()
        client.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)

        # ── Step 1: Get the best image for the card ────────────────────────
        thumb_blob = None
        og_url = _fetch_og_image_url(article_url)

        if og_url:
            print(f"[BLUESKY] OG image found: {og_url[:80]}")
            try:
                img_resp = requests.get(
                    og_url, timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                img_resp.raise_for_status()

                # Save temporarily
                tmp_path = Path("output/images/_bsky_thumb.jpg")
                tmp_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path.write_bytes(img_resp.content)

                upload_resp = client.upload_blob(img_resp.content)
                thumb_blob  = upload_resp.blob
                print("[BLUESKY] ✓ OG image uploaded as blob.")
            except Exception as img_err:
                print(f"[BLUESKY] OG image download failed ({img_err}), using local image.")

        # Fall back to DALL-E / RSS image already on disk
        if thumb_blob is None and image_path and Path(image_path).exists():
            print("[BLUESKY] Using local image as card thumbnail …")
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            # Skip blank placeholder files
            if len(img_bytes) > 1000:
                upload_resp = client.upload_blob(img_bytes)
                thumb_blob  = upload_resp.blob
                print("[BLUESKY] ✓ Local image uploaded as blob.")

        # ── Step 2: Build the external embed card ─────────────────────────
        embed = {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri":         article_url,
                "title":       article_title[:200],
                "description": (article_description or caption)[:400],
            },
        }
        if thumb_blob:
            embed["external"]["thumb"] = thumb_blob

        # ── Step 3: Post text + embed ──────────────────────────────────────
        # Keep caption clean (no raw URL — the card handles it)
        clean_caption = caption[:300]

        response = client.send_post(text=clean_caption, embed=embed)
        uri = response.uri
        print(f"[BLUESKY] ✓ Posted: {uri}")
        return {"status": "success", "uri": uri}

    except Exception as e:
        print(f"[BLUESKY] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── TikTok ────────────────────────────────────────────────────────────────────
def post_tiktok(caption: str, image_path: str) -> dict:
    print("[TIKTOK] Skipped — not configured.")
    return {"status": "skipped", "reason": "not configured"}


# ── Website (GitHub Pages JSON feed) ─────────────────────────────────────────
def post_website(headline: str, body: str, image_path: str, source_url: str) -> dict:
    print("[WEBSITE] Updating feed.json …")
    try:
        WEBSITE_FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if WEBSITE_FEED_PATH.exists():
            existing = json.loads(WEBSITE_FEED_PATH.read_text())

        img_dest = WEBSITE_FEED_PATH.parent / "images" / Path(image_path).name
        img_dest.parent.mkdir(parents=True, exist_ok=True)
        img_dest.write_bytes(Path(image_path).read_bytes())

        new_entry = {
            "id":         int(time.time()),
            "date":       datetime.now(timezone.utc).isoformat(),
            "headline":   headline,
            "body":       body,
            "image":      f"images/{img_dest.name}",
            "source_url": source_url,
        }
        existing.insert(0, new_entry)
        existing = existing[:30]
        WEBSITE_FEED_PATH.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
        print(f"[WEBSITE] ✓ feed.json updated ({len(existing)} entries)")
        return {"status": "success", "entries": len(existing)}
    except Exception as e:
        print(f"[WEBSITE] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Main: post to all platforms ───────────────────────────────────────────────
def post_all(captions: dict, image_path: str, source_url: str,
             article_title: str = "", article_description: str = "") -> dict:

    website_parts = captions["website"].split("\n\n", 1)
    headline = website_parts[0].strip()
    body     = website_parts[1].strip() if len(website_parts) > 1 else ""

    results = {
        "twitter":  post_twitter(captions["twitter"], image_path),
        "facebook": post_facebook(captions["facebook"], image_path),
        "bluesky":  post_bluesky(
                        caption=captions.get("bluesky", captions["twitter"]),
                        image_path=image_path,
                        article_url=source_url,
                        article_title=article_title or headline,
                        article_description=article_description or body[:300],
                    ),
        "tiktok":   post_tiktok(captions.get("tiktok", ""), image_path),
        "website":  post_website(headline, body, image_path, source_url),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\n── Posting Summary ──────────────────────")
    for platform, res in results.items():
        if platform == "timestamp":
            continue
        status = res.get("status", "unknown")
        emoji  = "✓" if status == "success" else ("⚠" if status == "skipped" else "✗")
        print(f"  {emoji} {platform.upper()}: {status}")

    return results  
