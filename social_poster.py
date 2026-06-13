"""
social_poster.py
Posts the AI-generated news content to:
• Twitter / X       (via Tweepy v4)
• Facebook Page     (via Graph API)
• Bluesky           (via atproto)
• Website           (via GitHub Pages JSON feed)
"""

import os
import json
import time
import requests
import tweepy
import re
from datetime import datetime, timezone
from pathlib import Path

# ── atproto for Bluesky ───────────────────────────────────────────────────────
try:
    from atproto import Client as BskyClient
    ATPROTO_AVAILABLE = True
except ImportError:
    ATPROTO_AVAILABLE = False
    print("[BLUESKY] atproto library not installed — skipping Bluesky.")

# ── Credentials ─────────────────────────────────────────────────────────────
TW_API_KEY          = os.environ.get("TWITTER_API_KEY", "")
TW_API_SECRET       = os.environ.get("TWITTER_API_SECRET", "")
TW_ACCESS_TOKEN     = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TW_ACCESS_SECRET    = os.environ.get("TWITTER_ACCESS_SECRET", "")

FB_PAGE_ID          = os.environ.get("FACEBOOK_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")

BLUESKY_HANDLE      = os.environ.get("BLUESKY_HANDLE", "")
BLUESKY_APP_PASSWORD = os.environ.get("BLUESKY_APP_PASSWORD", "")

WEBSITE_FEED_PATH   = Path("output/website/feed.json")

# ── Twitter / X ──────────────────────────────────────────────────────────────
def post_twitter(caption: str, image_path: str) -> dict:
    print("[TWITTER] Posting …")
    if not all([TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET]):
        return {"status": "skipped", "reason": "credentials missing"}
    try:
        auth   = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media  = api_v1.media_upload(filename=image_path)
        client = tweepy.Client(consumer_key=TW_API_KEY, consumer_secret=TW_API_SECRET, 
                               access_token=TW_ACCESS_TOKEN, access_token_secret=TW_ACCESS_SECRET)
        tweet  = client.create_tweet(text=caption[:280], media_ids=[media.media_id])
        return {"status": "success", "url": f"https://twitter.com/i/web/status/{tweet.data['id']}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ── Facebook Page ──────────────────────────────────────────────────────────
def post_facebook(caption: str, image_path: str) -> dict:
    print("[FACEBOOK] Posting …")
    if not all([FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN]):
        return {"status": "skipped", "reason": "credentials missing"}
    try:
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
        with open(image_path, "rb") as f:
            resp = requests.post(url, data={"caption": caption, "access_token": FB_PAGE_ACCESS_TOKEN}, 
                                 files={"source": f}, timeout=30)
        resp.raise_for_status()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ── Bluesky ────────────────────────────────────────────────────────────────
def post_bluesky(caption: str, image_path: str, article_url: str, article_title: str) -> dict:
    print("[BLUESKY] Posting …")
    if not ATPROTO_AVAILABLE or not BLUESKY_HANDLE:
        return {"status": "skipped"}
    try:
        client = BskyClient()
        client.login(BLUESKY_HANDLE, BLUESKY_APP_PASSWORD)
        
        with open(image_path, "rb") as f:
            thumb_blob = client.upload_blob(f.read()).blob
            
        embed = {
            "$type": "app.bsky.embed.external",
            "external": {"uri": article_url, "title": article_title[:200], "thumb": thumb_blob}
        }
        client.send_post(text=caption[:300], embed=embed)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# ── Website ────────────────────────────────────────────────────────────────
def post_website(headline: str, body: str, image_path: str, source_url: str) -> dict:
    WEBSITE_FEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(WEBSITE_FEED_PATH.read_text()) if WEBSITE_FEED_PATH.exists() else []
    
    new_entry = {
        "id": int(time.time()),
        "date": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "body": body,
        "image": f"images/{Path(image_path).name}",
        "source_url": source_url
    }
    existing.insert(0, new_entry)
    WEBSITE_FEED_PATH.write_text(json.dumps(existing[:30], indent=2, ensure_ascii=False))
    return {"status": "success"}

# ── Main ──────────────────────────────────────────────────────────────────
def post_all(captions: dict, image_path: str, source_url: str, article_title: str = "") -> dict:
    website_parts = captions["website"].split("\n\n", 1)
    headline = website_parts[0].strip()
    body = website_parts[1].strip() if len(website_parts) > 1 else ""

    return {
        "twitter":  post_twitter(captions["twitter"], image_path),
        "facebook": post_facebook(captions["facebook"], image_path),
        "bluesky":  post_bluesky(captions.get("bluesky", captions["twitter"]), image_path, source_url, article_title or headline),
        "website":  post_website(headline, body, image_path, source_url)
    }
