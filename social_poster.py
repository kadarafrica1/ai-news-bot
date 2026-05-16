"""
social_poster.py

Posts the AI-generated news content to:
• Twitter / X  (via Tweepy v4)     — Breaking News image overlay
• Bluesky      (via atproto SDK)   — FREE, no payment needed
• Facebook Page (via Graph API)    — high quality 1200x630 image

NOTE: Website posting removed — will connect to Blogger separately.
NOTE: No files are saved to GitHub repo after posting.
"""

import os
import requests
import tweepy
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from atproto import Client as BskyClient

# ── Credentials ───────────────────────────────────────────────────────────────
TW_API_KEY           = os.environ.get("TWITTER_API_KEY", "")
TW_API_SECRET        = os.environ.get("TWITTER_API_SECRET", "")
TW_ACCESS_TOKEN      = os.environ.get("TWITTER_ACCESS_TOKEN", "")
TW_ACCESS_SECRET     = os.environ.get("TWITTER_ACCESS_SECRET", "")
FB_PAGE_ID           = os.environ.get("FACEBOOK_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FACEBOOK_PAGE_ACCESS_TOKEN", "")
BSKY_HANDLE          = os.environ.get("BLUESKY_HANDLE", "")
BSKY_APP_PASSWORD    = os.environ.get("BLUESKY_APP_PASSWORD", "")

TARGET_W, TARGET_H = 1200, 630


# ── Image helpers ─────────────────────────────────────────────────────────────

def prepare_facebook_image(image_path: str) -> str:
    """Resize to 1200x630 high quality for Facebook."""
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        out = image_path.replace(".jpg", "_fb.jpg")
        img.save(out, "JPEG", quality=95)
        print("[IMG] Facebook image → 1200x630")
        return out
    except Exception as e:
        print(f"[WARN] FB resize failed: {e}")
        return image_path


def prepare_twitter_image(image_path: str, headline: str) -> str:
    """Add Al Jazeera-style Breaking News overlay."""
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((TARGET_W, TARGET_H), Image.LANCZOS)
        draw = ImageDraw.Draw(img)

        # Dark strip at bottom
        banner_h = 180
        banner_y = TARGET_H - banner_h
        img.paste(Image.new("RGB", (TARGET_W, banner_h), (0, 0, 0)),
                  (0, banner_y))

        try:
            font_bold = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
            font_headline = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        except Exception:
            font_bold = ImageFont.load_default()
            font_headline = font_bold

        # Red BREAKING NEWS pill
        pill_x, pill_y = 40, banner_y + 18
        draw.rectangle([pill_x, pill_y, pill_x + 270, pill_y + 44],
                       fill=(220, 30, 30))
        draw.text((pill_x + 16, pill_y + 8), "BREAKING NEWS",
                  font=font_bold, fill=(255, 255, 255))

        # Headline
        short = headline[:80] + ("…" if len(headline) > 80 else "")
        draw.text((40, banner_y + 75), short,
                  font=font_headline, fill=(255, 255, 255))

        out = image_path.replace(".jpg", "_tw.jpg")
        img.save(out, "JPEG", quality=95)
        print("[IMG] Twitter Breaking News overlay added")
        return out
    except Exception as e:
        print(f"[WARN] Twitter overlay failed: {e}")
        return image_path


def prepare_bluesky_image(image_path: str) -> str:
    """Bluesky max blob ≈ 976 KB — resize + compress."""
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((1000, 525), Image.LANCZOS)
        out = image_path.replace(".jpg", "_bsky.jpg")
        img.save(out, "JPEG", quality=85)
        print("[IMG] Bluesky image prepared (1000x525)")
        return out
    except Exception as e:
        print(f"[WARN] Bluesky image prep failed: {e}")
        return image_path


# ── Twitter / X ───────────────────────────────────────────────────────────────

def post_twitter(caption: str, image_path: str, headline: str) -> dict:
    print("[TWITTER] Posting …")
    if not all([TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET]):
        print("[TWITTER] ⚠ Credentials missing — skipped.")
        return {"status": "skipped", "reason": "missing credentials"}
    try:
        tw_image = prepare_twitter_image(image_path, headline)
        auth = tweepy.OAuth1UserHandler(
            TW_API_KEY, TW_API_SECRET, TW_ACCESS_TOKEN, TW_ACCESS_SECRET)
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=tw_image)
        client = tweepy.Client(
            consumer_key=TW_API_KEY, consumer_secret=TW_API_SECRET,
            access_token=TW_ACCESS_TOKEN, access_token_secret=TW_ACCESS_SECRET)
        tweet = client.create_tweet(text=caption[:280],
                                    media_ids=[media.media_id])
        tweet_id = tweet.data["id"]
        print(f"[TWITTER] ✓ Tweet ID: {tweet_id}")
        return {"status": "success", "tweet_id": tweet_id}
    except Exception as e:
        print(f"[TWITTER] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Bluesky ───────────────────────────────────────────────────────────────────

def post_bluesky(caption: str, image_path: str, source_url: str) -> dict:
    print("[BLUESKY] Posting …")
    if not all([BSKY_HANDLE, BSKY_APP_PASSWORD]):
        print("[BLUESKY] ⚠ Credentials missing — skipped.")
        return {"status": "skipped", "reason": "missing credentials"}
    try:
        bsky_image = prepare_bluesky_image(image_path)
        client = BskyClient()
        client.login(BSKY_HANDLE, BSKY_APP_PASSWORD)

        with open(bsky_image, "rb") as f:
            img_data = f.read()

        text = caption[:260] + f"\n\n{source_url}"
        text = text[:300]

        post = client.send_image(
            text=text,
            image=img_data,
            image_alt="Breaking news image",
        )
        print(f"[BLUESKY] ✓ Posted: {post.uri}")
        return {"status": "success", "uri": post.uri}
    except Exception as e:
        print(f"[BLUESKY] ✗ {e}")
        return {"status": "error", "error": str(e)}


# ── Facebook Page ─────────────────────────────────────────────────────────────

def post_facebook(caption: str, image_path: str) -> dict:
    print("[FACEBOOK] Posting …")
    if not all([FB_PAGE_ID, FB_PAGE_ACCESS_TOKEN]):
        print("[FACEBOOK] ⚠ Credentials missing — skipped.")
        return {"status": "skipped", "reason": "missing credentials"}
    try:
        fb_image = prepare_facebook_image(image_path)
        url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
        with open(fb_image, "rb") as f:
            resp = requests.post(
                url,
                data={"caption": caption,
                      "access_token": FB_PAGE_ACCESS_TOKEN},
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


# ── Main ──────────────────────────────────────────────────────────────────────

def post_all(captions: dict, image_path: str, source_url: str) -> dict:
    website_parts = captions.get("website", captions.get("twitter", "")).split("\n\n", 1)
    headline = website_parts[0].strip()

    results = {
        "twitter":  post_twitter(captions["twitter"], image_path, headline),
        "bluesky":  post_bluesky(captions["twitter"], image_path, source_url),
        "facebook": post_facebook(captions["facebook"], image_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print("\n── Posting Summary ──────────────────────")
    for platform, res in results.items():
        if platform == "timestamp":
            continue
        status = res.get("status", "unknown")
        emoji = "✓" if status == "success" else (
            "⚠" if status == "skipped" else "✗")
        print(f"  {emoji}  {platform.upper()}: {status}")

    return results
