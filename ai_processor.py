"""
ai_processor.py

Uses Groq AI to:
1. Pick the single most newsworthy story.
2. Identify the key person(s) involved.
3. Write platform-specific captions — each one separately to avoid JSON issues.
"""

import json
import re
import os
from typing import Dict, List
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"


def _call_groq(prompt: str, max_tokens: int = 400) -> str:
    """Call Groq and return plain text response."""
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def _call_groq_json(prompt: str, max_tokens: int = 200) -> dict | list:
    """
    Call Groq expecting SIMPLE JSON only (no hashtags, no quotes inside values).
    Used only for select_top_story and extract_key_people.
    """
    raw = _call_groq(prompt, max_tokens)
    # Strip markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()
    # Extract first { } or [ ] block
    for pattern in (r"\{[^{}]*\}", r"\[[^\[\]]*\]"):
        match = re.search(pattern, raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    # Try full raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse failed: {e}\nRaw: {raw[:300]}") from e


# ── Story selection ───────────────────────────────────────────────────────────

def select_top_story(articles: List[Dict]) -> Dict:
    articles_text = "\n\n".join(
        f"[{i+1}] SOURCE: {a['source']}\nTITLE: {a['title']}\n"
        f"SUMMARY: {a['summary']}\nURL: {a['url']}"
        for i, a in enumerate(articles)
    )
    prompt = f"""You are a senior news editor. Below are today's top candidate stories.

{articles_text}

Pick the SINGLE most globally significant story.
Reply ONLY with this exact JSON, no extra text, no markdown:
{{"selected_index": 1, "reason": "one sentence"}}"""

    data = _call_groq_json(prompt, max_tokens=150)
    story = articles[int(data["selected_index"]) - 1]
    story["selection_reason"] = data.get("reason", "")
    return story


def extract_key_people(story: Dict) -> List[str]:
    prompt = f"""List the 1-3 most prominent real people in this news story.
Reply ONLY with a JSON array like: ["Full Name", "Full Name"]
If none, reply: []
No markdown, no explanation.

TITLE: {story['title']}
SUMMARY: {story['summary']}"""

    names = _call_groq_json(prompt, max_tokens=80)
    return names if isinstance(names, list) else []


# ── Caption generation — each platform separately ────────────────────────────

def _gen_twitter(story: Dict, people_str: str) -> str:
    prompt = f"""Write a Twitter/X post about this news story.
- Max 220 characters (leave room for hashtags)
- Add 2-3 relevant hashtags at the end
- Factual and punchy
- NO source credit

STORY: {story['title']}
SUMMARY: {story['summary']}
PEOPLE: {people_str}

Reply with ONLY the tweet text, nothing else."""
    return _call_groq(prompt, max_tokens=120)


def _gen_facebook(story: Dict, people_str: str) -> str:
    prompt = f"""Write a Facebook post about this news story.
- 2-3 sentences
- Factual and informative
- NO hashtags
- NO source credit like "Credit: BBC"

STORY: {story['title']}
SUMMARY: {story['summary']}
PEOPLE: {people_str}

Reply with ONLY the Facebook post text, nothing else."""
    return _call_groq(prompt, max_tokens=150)


def _gen_tiktok(story: Dict, people_str: str) -> str:
    prompt = f"""Write a TikTok caption about this news story.
- Hook sentence first
- 3-4 short lines total
- Casual but factual
- 2 hashtags at end

STORY: {story['title']}
SUMMARY: {story['summary']}

Reply with ONLY the TikTok caption, nothing else."""
    return _call_groq(prompt, max_tokens=120)


def _gen_website(story: Dict, people_str: str) -> str:
    prompt = f"""Write a news article opening for this story.
- First line: Title Case headline
- Empty line
- Then 3-4 sentence journalistic intro paragraph
- NO source credit

STORY: {story['title']}
SUMMARY: {story['summary']}
PEOPLE: {people_str}

Reply with ONLY the headline and intro, nothing else."""
    return _call_groq(prompt, max_tokens=200)


def _gen_image_prompt(story: Dict, people_str: str) -> str:
    prompt = f"""Write a image generation prompt for this news story.
- Realistic editorial photo style
- Show {people_str} in context of the event
- 1-2 sentences only

STORY: {story['title']}

Reply with ONLY the image prompt, nothing else."""
    return _call_groq(prompt, max_tokens=80)


def generate_captions(story: Dict, people: List[str]) -> Dict[str, str]:
    """Generate each caption separately — no JSON parsing issues."""
    people_str = ", ".join(people) if people else "key figures"

    return {
        "twitter":      _gen_twitter(story, people_str),
        "facebook":     _gen_facebook(story, people_str),
        "tiktok":       _gen_tiktok(story, people_str),
        "website":      _gen_website(story, people_str),
        "image_prompt": _gen_image_prompt(story, people_str),
    }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def process_news(articles: List[Dict]) -> Dict:
    print("[AI] Selecting top story …")
    story = select_top_story(articles)
    print(f"[AI] Selected: {story['title']}")

    print("[AI] Extracting key people …")
    people = extract_key_people(story)
    print(f"[AI] People: {people}")

    print("[AI] Generating captions …")
    captions = generate_captions(story, people)

    return {
        "story":    story,
        "people":   people,
        "captions": captions,
    }


if __name__ == "__main__":
    from news_fetcher import get_top_articles
    articles = get_top_articles(5)
    result = process_news(articles)
    print(json.dumps(result, indent=2, default=str))
