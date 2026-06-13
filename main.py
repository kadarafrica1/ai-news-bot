"""
main.py
Orchestrator — runs the full pipeline
"""

import sys
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path

from news_fetcher import get_top_articles
from ai_processor import process_news
from image_handler import get_news_image
from social_poster import post_all

TEMP_DIR = Path("temp_output")

def cleanup():
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
        print("[CLEANUP] ✓ Temp files deleted")

def run():
    print(f"\n{'='*55}\n  AI NEWS BOT — {datetime.now(timezone.utc)}\n{'='*55}\n")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────────
        print("── Step 1: Fetching articles ─────────────────────────")
        articles = get_top_articles(n=8)
        if not articles:
            sys.exit(1)

        # ── 2. AI Processing ──────────────────────────────────────────────
        print("\n── Step 2: AI processing ─────────────────────────────")
        result = process_news(articles)
        story    = result["story"]
        captions = result["captions"]
        people   = result.get("people", [])

        # ── 3. Image ──────────────────────────────────────────────────────
        print("\n── Step 3: Fetching image ────────────────────────────")
        google_query = (" ".join(people[:2]) + " " + story["title"][:60]) if people else story["title"][:80]
        
        # Halkan ayaan ku saxay wicitaanka get_news_image
        image_path = get_news_image(
            dalle_prompt="", 
            google_query=google_query,
            rss_thumbnail_url=story.get("image", ""),
            article_url=story.get("url", ""),
            filename="current_news_image"
        )
        
        # ── 4. Post ───────────────────────────────────────────────────────
        print("\n── Step 4: Posting to all platforms ──────────────────")
        post_all(captions, image_path, story["url"], article_title=story["title"])

        print(f"\n{'='*55}\n  PIPELINE COMPLETED SUCCESSFULLY\n{'='*55}\n")

    finally:
        cleanup()

if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("\n[FATAL ERROR]")
        traceback.print_exc()
        cleanup()
        sys.exit(1)
