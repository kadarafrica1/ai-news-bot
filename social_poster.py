"""
social_poster.py
Posts the AI-generated news content to:
  • Twitter / X   (via Tweepy v4)
  • Facebook Page (via Graph API)
  • TikTok        (via TikTok Content Posting API)
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

TIKTOK_ACCESS_TOKEN   = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

WEBSITE_FEED_PATH     = Path("output/website/feed.json")


# ── Twitter / X ───────────────────────────────────────────────────────────────

def post_twitter(caption: str, image_path: str) -> dict:
    print("[TWITTER] Posting …")
    try:
        # v1 client for media upload
        auth = tweepy.OAuth1UserHandler(TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media  = api_v1.media_upload(filename=image_path)

        # v2 client for tweet
        client = tweepy.Client(
            consumer_key=TW_API_KEY,
            consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN,
            access_token_secret=TW_ACCESS_SECRET,
        )
        tweet = client.create_tweet(text=caption[:280], media_ids=[media.media_id])
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
        # Upload photo with caption
        url  = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
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
    """
    TikTok Content Posting API (photo post / slideshow).
    Requires: TikTok for Developers app with content.publish scope.
    """
    print("[TIKTOK] Posting …")
    if not TIKTOK_ACCESS_TOKEN:
        print("[TIKTOK] No access token — skipping.")
        return {"status": "skipped", "reason": "no token"}
    try:
        # Step 1: Initialize photo upload
        init_url  = "https://open.tiktokapis.com/v2/post/publish/content/init/"
        init_body = {
            "post_info": {
                "title":           caption[:150],
                "privacy_level":   "PUBLIC_TO_EVERYONE",
                "disable_comment": False,
            },
            "source_info": {
                "source":     "FILE_UPLOAD",
                "video_size": os.path.getsize(image_path),  # not used for photos but required
            },
            "media_type": "PHOTO",
        }
        headers = {"Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}", "Content-Type": "application/json"}
        init_resp = requests.post(init_url, json=init_body, headers=headers, timeout=20)
        init_resp.raise_for_status()
        data       = init_resp.json().get("data", {})
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")

        # Step 2: Upload the image
        with open(image_path, "rb") as f:
            upload_resp = requests.put(upload_url, data=f, headers={"Content-Type": "image/jpeg"}, timeout=30)
        upload_resp.raise_for_status()

        print(f"[TIKTOK] ✓ Publish ID: {publish_id}")
        return {"status": "success", "publish_id": publish_id}
    except Exception as e:
        print(f"[TIKTOK] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Website (GitHub Pages JSON feed) ─────────────────────────────────────────

def post_website(headline: str, body: str, image_path: str, source_url: str) -> dict:
    """
    Append a new entry to output/website/feed.json.
    GitHub Actions will commit this file; the static site reads it.
    """
    print("[WEBSITE] Updating feed.json …")
    try:
        WEBSITE_FEED_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Load existing feed
        existing = []
        if WEBSITE_FEED_PATH.exists():
            existing = json.loads(WEBSITE_FEED_PATH.read_text())

        # Copy image to website assets
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

        # Prepend (newest first), keep last 30 entries
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
    """Run all platform posts and return a summary."""
    # Parse website caption (headline + body split by newline)
    website_parts = captions["website"].split("\n\n", 1)
    headline      = website_parts[0].strip()
    body          = website_parts[1].strip() if len(website_parts) > 1 else ""

    results = {
        "twitter":  post_twitter(captions["twitter"], image_path),
        "facebook": post_facebook(captions["facebook"], image_path),
        "tiktok":   post_tiktok(captions["tiktok"], image_path),
        "website":  post_website(headline, body, image_path, source_url),
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
