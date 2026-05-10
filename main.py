"""
main.py
Orchestrator — runs the full pipeline:
  1. Fetch articles from major news outlets
  2. AI selects the top story + generates captions
  3. Image is created (DALL-E first, Google fallback, RSS thumbnail last)
  4. Post to Twitter, Facebook, TikTok, and the website feed
  5. Save a run report to output/report_YYYYMMDD.json
"""

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from news_fetcher  import get_top_articles
from ai_processor  import process_news
from image_handler import get_news_image
from social_poster import post_all

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def run():
    run_time = datetime.now(timezone.utc)
    print(f"\n{'='*55}")
    print(f"  AI NEWS BOT  —  {run_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*55}\n")

    report = {"run_time": run_time.isoformat(), "status": "started"}

    # ── 1. Fetch ──────────────────────────────────────────────────────────────
    print("── Step 1: Fetching articles ─────────────────────────")
    articles = get_top_articles(n=8)
    if not articles:
        print("[ERROR] No articles fetched. Aborting.")
        sys.exit(1)

    # ── 2. AI Processing ─────────────────────────────────────────────────────
    print("\n── Step 2: AI processing ─────────────────────────────")
    result   = process_news(articles)
    story    = result["story"]
    people   = result["people"]
    captions = result["captions"]
    report["story"]   = story
    report["people"]  = people

    # ── 3. Image ─────────────────────────────────────────────────────────────
    print("\n── Step 3: Generating / fetching image ───────────────")
    dalle_prompt  = captions.get("image_prompt", story["title"])
    google_query  = " ".join(people[:2]) + " " + story["title"][:60] if people else story["title"][:80]
    image_path    = get_news_image(
        dalle_prompt      = dalle_prompt,
        google_query      = google_query,
        rss_thumbnail_url = story.get("image_url", ""),
        filename          = f"news_{run_time.strftime('%Y%m%d')}",
    )
    report["image_path"] = image_path

    # ── 4. Post ───────────────────────────────────────────────────────────────
    print("\n── Step 4: Posting to all platforms ──────────────────")
    post_results  = post_all(captions, image_path, story["url"])
    report["posts"] = post_results

    # ── 5. Save report ────────────────────────────────────────────────────────
    report["status"] = "completed"
    report_path = OUTPUT_DIR / f"report_{run_time.strftime('%Y%m%d_%H%M')}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False))
    print(f"\n[✓] Report saved → {report_path}")

    print(f"\n{'='*55}")
    print("  PIPELINE COMPLETED SUCCESSFULLY")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        print("\n[FATAL ERROR]")
        traceback.print_exc()
        sys.exit(1)
