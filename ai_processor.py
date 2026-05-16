"""
ai_processor.py

Uses Groq AI to:
1. Pick the single most newsworthy story.
2. Identify the key person(s) involved.
3. Write platform-specific captions in journalistic style.
"""

import json
import re
import os
from typing import Dict, List
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.3-70b-versatile"


def _call_groq(prompt: str, max_tokens: int = 800) -> str:
    """Helper: call Groq and return the text response."""
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.4,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def _safe_json(raw: str) -> dict | list:
    """
    Robustly extract JSON from Groq response.
    Handles markdown fences, extra text, smart quotes, etc.
    """
    # 1. Strip markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()

    # 2. Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 3. Extract the first {...} or [...] block
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, raw)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    # 4. Replace smart quotes and try again
    cleaned = raw.replace("\u2018", "'").replace("\u2019", "'") \
                 .replace("\u201c", '"').replace("\u201d", '"')
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 5. Last resort — remove any non-printable characters
    cleaned = re.sub(r"[^\x20-\x7E\n\r\t]", "", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse JSON from Groq response.\n"
                         f"Error: {e}\nRaw response:\n{raw[:500]}") from e


def select_top_story(articles: List[Dict]) -> Dict:
    """Ask Groq to choose the single most important story."""
    articles_text = "\n\n".join(
        f"[{i+1}] SOURCE: {a['source']}\nTITLE: {a['title']}\n"
        f"SUMMARY: {a['summary']}\nURL: {a['url']}"
        for i, a in enumerate(articles)
    )

    prompt = f"""You are a senior news editor. Below are today's top candidate stories.

{articles_text}

Pick the SINGLE most globally significant, high-impact story.

Reply ONLY with valid JSON — no markdown, no explanation:

{{
  "selected_index": <1-based integer>,
  "reason": "<one sentence why this is the most important>"
}}"""

    raw = _call_groq(prompt, max_tokens=200)
    data = _safe_json(raw)
    story = articles[data["selected_index"] - 1]
    story["selection_reason"] = data["reason"]
    return story


def extract_key_people(story: Dict) -> List[str]:
    """Extract the main person / people the story is about."""
    prompt = f"""Extract the 1-3 most prominent real people mentioned in this news story.

Return ONLY a JSON array of full names, e.g. ["Donald Trump", "Xi Jinping"].
If no specific person, return [].

TITLE: {story['title']}
SUMMARY: {story['summary']}"""

    raw = _call_groq(prompt, max_tokens=100)
    names = _safe_json(raw)
    return names if isinstance(names, list) else []


def generate_captions(story: Dict, people: List[str]) -> Dict[str, str]:
    """Generate platform-optimised captions."""
    people_str = ", ".join(people) if people else "key figures"

    prompt = f"""You are a professional news writer. Write captions for this story.

IMPORTANT RULES:
- Do NOT include any source credit like "Credit: BBC" or "Source:" anywhere
- Do NOT mention where the story came from
- Write as if you are the original news publisher
- Use ONLY standard double quotes for JSON strings
- Do NOT use apostrophes inside JSON string values — reword to avoid them
- Keep language clear, factual, and impactful

STORY TITLE: {story['title']}
STORY SUMMARY: {story['summary']}
KEY PEOPLE: {people_str}

Return ONLY valid JSON with these five keys — no markdown, no explanation:

{{
  "twitter": "<max 240 chars, punchy, 2-3 relevant hashtags>",
  "facebook": "<2-3 sentences, informative, factual, no hashtags, no source credit>",
  "tiktok": "<hook in first line, casual but factual, 3-4 lines, 2 hashtags>",
  "website": "<headline in Title Case>\\n\\n<3-4 sentence article intro>",
  "image_prompt": "<detailed editorial photo prompt showing {people_str} in context of this news>"
}}"""

    raw = _call_groq(prompt, max_tokens=900)
    return _safe_json(raw)


def process_news(articles: List[Dict]) -> Dict:
    """Full pipeline: select → extract people → generate captions."""
    print("[AI] Selecting top story …")
    story = select_top_story(articles)
    print(f"[AI] Selected: {story['title']}")

    print("[AI] Extracting key people …")
    people = extract_key_people(story)
    print(f"[AI] People: {people}")

    print("[AI] Generating captions …")
    captions = generate_captions(story, people)

    return {
        "story": story,
        "people": people,
        "captions": captions,
    }


if __name__ == "__main__":
    from news_fetcher import get_top_articles
    articles = get_top_articles(5)
    result = process_news(articles)
    print(json.dumps(result, indent=2, default=str))
