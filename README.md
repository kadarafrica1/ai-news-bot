# 🤖 AI Daily News Bot

Automatically fetches the day's most important news, writes journalistic captions using Claude AI, generates editorial images with DALL-E, and posts to **Twitter/X**, **Facebook**, **TikTok**, and a **GitHub Pages website** — every day at **8 PM UTC**.

---

## 📁 File Structure

```
ai-news-bot/
├── main.py              # Orchestrator — runs the full pipeline
├── news_fetcher.py      # Pulls articles from BBC, CNN, Al Jazeera, etc.
├── ai_processor.py      # Claude AI selects top story + writes captions
├── image_handler.py     # DALL-E 3 image → Google Images fallback → RSS thumbnail
├── social_poster.py     # Posts to Twitter, Facebook, TikTok, website
├── requirements.txt
├── output/
│   └── website/
│       ├── index.html   # Beautiful news website (GitHub Pages)
│       └── feed.json    # Auto-updated article feed
└── .github/
    └── workflows/
        └── daily_news.yml  # Runs every day at 20:00 UTC
```

---

## 🚀 Setup (Step by Step)

### 1. Fork / Create the GitHub Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-news-bot.git
cd ai-news-bot
```

### 2. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add each of these:

| Secret Name | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `TWITTER_API_KEY` | https://developer.twitter.com (create app, get Keys & Tokens) |
| `TWITTER_API_SECRET` | same |
| `TWITTER_ACCESS_TOKEN` | same (generate for your account) |
| `TWITTER_ACCESS_SECRET` | same |
| `FACEBOOK_PAGE_ID` | Your Facebook Page ID (in Page settings) |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | https://developers.facebook.com → your app → Graph API Explorer |
| `TIKTOK_ACCESS_TOKEN` | https://developers.tiktok.com (Content Posting API) |
| `GOOGLE_API_KEY` | https://console.cloud.google.com (Custom Search API) *(optional)* |
| `GOOGLE_CX` | https://programmablesearchengine.google.com *(optional)* |

> **TikTok** and **Google Images** secrets are optional. The bot works without them (DALL-E will be the image source; TikTok will be skipped).

### 3. Enable GitHub Pages

Go to **Settings → Pages → Source → Deploy from branch** and select:
- Branch: `main`
- Folder: `/output/website`

Your news site will be live at:
```
https://YOUR_USERNAME.github.io/ai-news-bot/
```

### 4. Push and Test

```bash
git add .
git commit -m "Initial setup"
git push
```

To run immediately without waiting for 8 PM:
- Go to **Actions → AI Daily News Bot → Run workflow**

---

## ⚙️ Customising

### Change posting time
Edit `daily_news.yml`:
```yaml
- cron: "0 20 * * *"   # 20:00 UTC = 8 PM UTC
```
Use https://crontab.guru to set any time you want.

### Add / remove news sources
Edit `news_fetcher.py` → `RSS_FEEDS` dictionary.

### Change priority keywords
Edit `news_fetcher.py` → `PRIORITY_KEYWORDS` list.

### Change number of stories fetched
Edit `main.py`:
```python
articles = get_top_articles(n=8)   # increase for more candidates
```

---

## 🔄 How it Works

```
Every day at 8 PM UTC
       │
       ▼
[1] news_fetcher.py
    BBC, CNN, Al Jazeera, Reuters, AP, NBC, Guardian, Fox
    → scores each article by priority keywords
    → returns top 8 candidates
       │
       ▼
[2] ai_processor.py  (Claude AI)
    → picks the single most important story
    → extracts key people (e.g. "Donald Trump", "Xi Jinping")
    → writes captions for Twitter, Facebook, TikTok, Website
    → writes DALL-E image prompt
       │
       ▼
[3] image_handler.py
    → DALL-E 3 (editorial photo style)
    → fallback: Google Images search
    → fallback: RSS feed thumbnail
       │
       ▼
[4] social_poster.py
    → Twitter/X  (image + caption + hashtags)
    → Facebook   (photo post with caption)
    → TikTok     (photo post)
    → Website    (updates feed.json → GitHub Pages site)
       │
       ▼
[5] GitHub Actions commits output/ back to repo
    Website updates automatically
```

---

## 📝 Notes

- **Cost estimate per day**: ~$0.05–0.15 (Claude Opus + DALL-E 3 combined)
- **Rate limits**: Twitter free tier allows 1 post/day; upgrade for more
- **Facebook**: requires your app to be in **Live mode** and your page to be published
- **TikTok**: Content Posting API requires applying for access at developers.tiktok.com
