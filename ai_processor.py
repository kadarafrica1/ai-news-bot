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
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.3,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def _fix_json_string(raw: str) -> str:
    """
    Fix common JSON issues from LLM responses:
    - Smart quotes â†’ standard quotes
    - Unescaped double quotes inside string values â†’ escaped
    - Trailing commas
    """
    # Strip markdown fences
    raw = re.sub(r"```json|```", "", raw).strip()

    # Replace smart/curly quotes
    raw = raw.replace("\u201c", '\\"').replace("\u201d", '\\"')
    raw = raw.replace("\u2018", "'").replace("\u2019", "'")

    # Fix unescaped double quotes inside JSON string values
    # Strategy: find each "key": "value" pair and escape inner quotes
    def escape_value(m):
        key = m.group(1)
        val = m.group(2)
        # Escape any unescaped double quotes inside the value
        val = re.sub(r'(?<!\\)"', '\\"', val)
        return f'"{key}": "{val}"'

    # Apply to each key-value pair (handles multi-line values too)
    raw = re.sub(
        r'"(\w+)":\s*"((?:[^"\\]|\\.)*)"',
        escape_value,
        raw,
        flags=re.DOTALL,
    )

    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    return raw


def _safe_json(raw: str) -> dict | list:
    """Robustly extract and parse JSON from Groq response."""

    # Step 1: Try direct parse after basic cleanup
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Step 2: Apply aggressive string fixing
    try:
        fixed = _fix_json_string(raw)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Step 3: Extract first {...} block and fix it
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            block = _fix_json_string(match.group())
            return json.loads(block)
        except json.JSONDecodeError:
            pass

    # Step 4: Use json5-style lenient parsing â€” replace all inner quotes
    # Find JSON object, then sanitize each value
    try:
        # Remove all double quotes inside values by finding key-value pairs
        sanitized = re.sub(
            r'("(?:twitter|facebook|tiktok|website|image_prompt|reason)":\s*")([^"]*(?:"[^"]*"[^"]*)*?)(")',
            lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3),
            cleaned,
            flags=re.DOTALL,
        )
        return json.loads(sanitized)
    except Exception:
        pass

    raise ValueError(
        f"Could not parse JSON after all attempts.\n"
        f"Raw (first 400 chars):\n{raw[:400]}"
    )


def select_top_story(articles: List[Dict]) -> Dict:
    articles_text = "\n\n".join(
        f"[{i+1}] SOURCE: {a['source']}\nTITLE: {a['title']}\n"
        f"SUMMARY: {a['summary']}\nURL: {a['url']}"
        for i, a in enumerate(articles)
    )

    prompt = f"""You are a senior news editor. Below are today's top candidate stories.

{articles_text}

Pick the SINGLE most globally significant story.

Reply ONLY with this exact JSON format, no extra text:
{{"selected_index": 1, "reason": "one sentence here"}}"""

    raw = _call_groq(prompt, max_tokens=150)
    data = _safe_json(raw)
    story = articles[data["selected_index"] - 1]
    story["selection_reason"] = data["reason"]
    return story


def extract_key_people(story: Dict) -> List[str]:
    prompt = f"""List the 1-3 most prominent real people in this news story.

Reply ONLY with a JSON array like: ["Full Name", "Full Name"]
If none, reply: []

TITLE: {story['title']}
SUMMARY: {story['summary']}"""

    raw = _call_groq(prompt, max_tokens=80)
    names = _safe_json(raw)
    return names if isinstance(names, list) else []


def generate_captions(story: Dict, people: List[str]) -> Dict[str, str]:
    people_str = ", ".join(people) if people else "key figures"

    prompt = f"""You are a professional news writer. Create social media captions.

CRITICAL JSON RULES:
- Return ONLY the JSON object, nothing else
- Use ONLY escaped quotes inside strings: use \\\" never raw "
- Instead of quoting someone, paraphrase them (no inner quotes needed)
- Do NOT include source credits like Credit: BBC

STORY: {story['title']}
SUMMARY: {story['summary']}
PEOPLE: {people_str}

Return this exact JSON structure:
{{
  "twitter": "max 240 chars tweet with 2-3 hashtags",
  "facebook": "2-3 sentence factual post no hashtags",
  "tiktok": "short hook first line then 3 lines then 2 hashtags",
  "website": "Title Case Headline\\n\\n3-4 sentence article intro",
  "image_prompt": "detailed editorial photo prompt"
}}"""

    raw = _call_groq(prompt, max_tokens=900)
    return _safe_json(raw)


def process_news(articles: List[Dict]) -> Dict:
    print("[AI] Selecting top story â€¦")
    story = select_top_story(articles)
    print(f"[AI] Selected: {story['title']}")

    print("[AI] Extracting key people â€¦")
    people = extract_key_people(story)
    print(f"[AI] People: {people}")

    print("[AI] Generating captions â€¦")
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
