"""
main.py

Orchestrator — runs the full pipeline:
1. Fetch articles from major news outlets
2. AI selects the top story + generates captions
3. Fetch image (RSS thumbnail or placeholder)
4. Post to Twitter, Bluesky, Facebook
5. Clean up all temp files (no GitHub storage used)
"""

import json
import sys
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from news_fetcher import get_top_articles
from ai_processor import process_news
from image_handler import get_news_image
from social_poster import post_all

# Temp folder — only used during the run, deleted after
TEMP_DIR = Path("temp_output")


def cleanup():
    """Delete all temp files so nothing is saved to the repo."""
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        print("[CLEANUP] ✓ Temp files deleted — nothing saved to GitHub")


def run():
    run_time = datetime.now(timezone.utc)
    print(f"\n{'='*55}")
    print(f"  AI NEWS BOT — {run_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}\n")

    # Create temp dir for this run only
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────────
        print("── Step 1: Fetching articles ─────────────────────────")
        articles = get_top_articles(n=8)
        if not articles:
            print("[ERROR] No articles fetched. Aborting.")
            sys.exit(1)

        # ── 2. AI Processing ──────────────────────────────────────────────
        print("\n── Step 2: AI processing ─────────────────────────────")
        result = process_news(articles)
        story    = result["story"]
        captions = result["captions"]

        # ── 3. Image ──────────────────────────────────────────────────────
        print("\n── Step 3: Fetching image ────────────────────────────")
        people = result.get("people", [])
        google_query = (
            " ".join(people[:2]) + " " + story["title"][:60]
            if people else story["title"][:80]
        )
        
        
         # U beddel:
        image_path = get_news_image(
            dalle_prompt=...,
            google_query=...,
            rss_thumbnail_url=article.get("image", ""),
            article_url=article["url"],   # ← ku dar kan
        )
        # ── 4. Post ───────────────────────────────────────────────────────
        print("\n── Step 4: Posting to all platforms ──────────────────")
        post_results = post_all(captions, image_path, story["url"])

        # ── 5. Summary ────────────────────────────────────────────────────
        print(f"\n{'='*55}")
        print("  PIPELINE COMPLETED SUCCESSFULLY")
        print(f"{'='*55}\n")

    finally:
        # Always clean up — even if something crashed
        cleanup()


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("\n[FATAL ERROR]")
        traceback.print_exc()
        cleanup()
        sys.exit(1)
