"""
social_poster.py
Posts the AI-generated news content to:
  • Twitter / X   (via Tweepy v4)
  • Facebook Page (via Graph API)
  • Website       (via GitHub Pages JSON feed — auto-rendered by the site)
"""

import os
import json
import time
import requests
import tweepy
from datetime import datetime, timezone
from pathlib import Path

# ── Credentials from environment variables ────────────────────────────────────
TW_API_KEY            = os.environ["TWITTER_API_KEY"]
TW_API_SECRET         = os.environ["TWITTER_API_SECRET"]
TW_ACCESS_TOKEN       = os.environ["TWITTER_ACCESS_TOKEN"]
TW_ACCESS_SECRET      = os.environ["TWITTER_ACCESS_SECRET"]

FB_PAGE_ID            = os.environ["FACEBOOK_PAGE_ID"]
FB_PAGE_ACCESS_TOKEN  = os.environ["FACEBOOK_PAGE_ACCESS_TOKEN"]

WEBSITE_FEED_PATH     = Path("output/website/feed.json")


# ── Twitter / X ───────────────────────────────────────────────────────────────

def post_twitter(caption: str, image_path: str) -> dict:
    print("[TWITTER] Posting …")
    try:
        # v1 client for media upload
        auth   = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media  = api_v1.media_upload(filename=image_path)

        # v2 client for tweet
        client = tweepy.Client(
            consumer_key=TW_API_KEY,
            consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN,
            access_token_secret=TW_ACCESS_SECRET,
        )
        tweet    = client.create_tweet(text=caption[:280], media_ids=[media.media_id])
        tweet_id = tweet.data["id"]
        print(f"[TWITTER] ✓ Tweet ID: {tweet_id}")
        return {"status": "success", "tweet_id": tweet_id, "url": f"https://twitter.com/i/web/status/{tweet_id}"}
    except Exception as e:
        print(f"[TWITTER] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Facebook Page ─────────────────────────────────────────────────────────────

def post_facebook(caption: str, image_path: str) -> dict:
    print("[FACEBOOK] Posting …")
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

def post_all(captions: dict, image_path: str, source_url: str) -> dict:
    website_parts = captions["website"].split("\n\n", 1)
    headline      = website_parts[0].strip()
    body          = website_parts[1].strip() if len(website_parts) > 1 else ""

    results = {
        "twitter":   post_twitter(captions["twitter"], image_path),
        "facebook":  post_facebook(captions["facebook"], image_path),
        "tiktok":    post_tiktok(captions["tiktok"], image_path),
        "website":   post_website(headline, body, image_path, source_url),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\n── Posting Summary ──────────────────────")
    for platform, res in results.items():
        if platform == "timestamp":
            continue
        status = res.get("status", "unknown")
        emoji  = "✓" if status == "success" else ("⚠" if status == "skipped" else "✗")
        print(f"  {emoji}  {platform.upper()}: {status}")

    return results
