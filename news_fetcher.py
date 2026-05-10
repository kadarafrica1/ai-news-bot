"""
news_fetcher.py
Fetches top news from major outlets using RSS feeds and NewsAPI.
"""

import feedparser
import requests
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict

# ── RSS feeds from major outlets ─────────────────────────────────────────────
RSS_FEEDS = {
    "Al Jazeera":  "https://www.aljazeera.com/xml/rss/all.xml",
    "BBC":         "http://feeds.bbci.co.uk/news/world/rss.xml",
    "CNN":         "http://rss.cnn.com/rss/edition_world.rss",
    "NBC News":    "https://feeds.nbcnews.com/nbcnews/public/news",
    "Reuters":     "https://feeds.reuters.com/reuters/topNews",
    "AP News":     "https://feeds.apnews.com/ApNews/apf-topnews",
    "The Guardian":"https://www.theguardian.com/world/rss",
    "Fox News":    "https://moxie.foxnews.com/google-publisher/world.xml",
}

# ── Priority keywords (the more matches, the higher the score) ───────────────
PRIORITY_KEYWORDS = [
    "trump", "president", "war", "attack", "nuclear", "crisis", "election",
    "breaking", "urgent", "exclusive", "dead", "killed", "explosion",
    "ceasefire", "sanctions", "israel", "gaza", "ukraine", "russia", "china",
    "iran", "nato", "white house", "congress", "senate", "supreme court",
    "assassination", "coup", "protest", "collapse", "emergency",
]


def fetch_rss_articles(max_per_feed: int = 10) -> List[Dict]:
    """Pull recent articles from every RSS feed."""
    articles = []
    cutoff = datetime.utcnow() - timedelta(hours=24)

    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                # Parse publish date (fall back to now if missing)
                published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") and entry.published_parsed else datetime.utcnow()
                if published < cutoff:
                    continue

                articles.append({
                    "source":      source,
                    "title":       entry.get("title", ""),
                    "summary":     entry.get("summary", ""),
                    "url":         entry.get("link", ""),
                    "published":   published.isoformat(),
                    "image_url":   _extract_image(entry),
                })
        except Exception as e:
            print(f"[WARN] Could not fetch {source}: {e}")

    print(f"[INFO] Fetched {len(articles)} articles from {len(RSS_FEEDS)} sources")
    return articles


def score_article(article: Dict) -> int:
    """Score an article based on keyword matches in title + summary."""
    text = (article["title"] + " " + article["summary"]).lower()
    return sum(kw in text for kw in PRIORITY_KEYWORDS)


def get_top_articles(n: int = 5) -> List[Dict]:
    """Return the top-n most newsworthy articles of the day."""
    articles = fetch_rss_articles()
    scored   = sorted(articles, key=score_article, reverse=True)
    top      = scored[:n]
    for a in top:
        a["priority_score"] = score_article(a)
    return top


def _extract_image(entry) -> str:
    """Try to grab a thumbnail URL from the RSS entry."""
    # media:thumbnail
    if hasattr(entry, "media_thumbnail") and entry.media_thumbnail:
        return entry.media_thumbnail[0].get("url", "")
    # enclosure
    if hasattr(entry, "enclosures") and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get("type", "").startswith("image"):
                return enc.get("url", "")
    return ""


if __name__ == "__main__":
    top = get_top_articles(5)
    print(json.dumps(top, indent=2, default=str))
