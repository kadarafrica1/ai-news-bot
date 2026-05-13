"""
ai_processor.py

Uses Google Gemini AI to:
1. Pick the single most newsworthy story.
2. Identify the key person(s) involved.
3. Write platform-specific captions in journalistic style.
"""

import google.generativeai as genai
import json
import os
from typing import Dict, List

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-2.0-flash"


def _call_gemini(prompt: str, max_tokens: int = 800) -> str:
    """Helper: call Gemini and return the text response."""
    model = genai.GenerativeModel(
        MODEL,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.4,
        ),
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def select_top_story(articles: List[Dict]) -> Dict:
    """Ask Gemini to choose the single most important story."""
    articles_text = "\n\n".join(
        f"[{i+1}] SOURCE: {a['source']}\nTITLE: {a['title']}\nSUMMARY: {a['summary']}\nURL: {a['url']}"
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

    raw = _call_gemini(prompt, max_tokens=200)
    # Strip any accidental markdown fences
    raw = raw.replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)
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

    raw = _call_gemini(prompt, max_tokens=100)
    raw = raw.replace("```json", "").replace("```", "").strip()
    names = json.loads(raw)
    return names if isinstance(names, list) else []


def generate_captions(story: Dict, people: List[str]) -> Dict[str, str]:
    """Generate platform-optimised captions in the style of major news outlets."""
    people_str = ", ".join(people) if people else "key figures"

    prompt = f"""You are a professional news writer. Write captions for this story in the style of BBC / Reuters.

Keep language clear, factual, and impactful.

STORY TITLE: {story['title']}
STORY SUMMARY: {story['summary']}
KEY PEOPLE: {people_str}
SOURCE: {story['source']}

Return ONLY valid JSON with these four keys:

{{
  "twitter": "<max 240 chars, punchy, 2-3 relevant hashtags>",
  "facebook": "<2-3 sentences, informative, no hashtags, ends with source credit>",
  "tiktok": "<hook in first line, casual but factual, 3-4 lines, 2 hashtags>",
  "website": "<headline (Title Case)>\\n\\n<3-4 sentence article intro, journalistic style>",
  "image_prompt": "<detailed image prompt: realistic editorial photo style showing {people_str} in context of this news event>"
}}"""

    raw = _call_gemini(prompt, max_tokens=800)
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


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
