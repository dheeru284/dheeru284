"""Generate post ideas + copy for a page, using past performance to steer topics."""
from . import llm

POST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["topic", "hook", "slides", "reel_script", "caption", "hashtags",
                 "image_queries", "sources", "contains_affiliate"],
    "properties": {
        "topic": {"type": "string"},
        "hook": {"type": "string"},
        "slides": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["heading", "body"],
            "properties": {"heading": {"type": "string"}, "body": {"type": "string"}}}},
        "reel_script": {"type": "array", "items": {"type": "string"}},
        "caption": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "image_queries": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
        "contains_affiliate": {"type": "boolean"},
    },
}

SYSTEM = """You are the head writer for a faceless Instagram page in India.
Write ORIGINAL content only: never copy other creators, film/TV scripts, song lyrics or copyrighted characters.
Follow Instagram Community Guidelines, India's IT Rules 2021 and ASCI influencer guidelines:
- no hate, communal, casteist or religious mockery; no political campaigning
- no medical, legal or investment advice; no get-rich-quick or misleading claims
- facts must be accurate and verifiable; list sources
- if you mention a product to buy, set contains_affiliate=true
Write all on-screen text, script and caption in the requested language and its native script.
image_queries must be short ENGLISH stock-photo search terms (one per slide)."""


def generate(page, fmt, model, past_topics, top_topics):
    if llm.fake_enabled():
        return _fake(page, fmt)
    n_slides = "6-8" if fmt == "carousel" else "4-6"
    prompt = f"""Page niche: {page['niche']}
Language: {page['language']}
Style: {page['style']}
Format: {fmt} ({'swipeable carousel' if fmt == 'carousel' else '20-40 second voiceover Reel'})

Write one post with {n_slides} slides (heading <= 8 words, body <= 30 words).
reel_script: one voiceover line per slide, conversational, first line is the hook.
caption: hook line, 2-4 short value lines, a call to action (save/share/follow), <= 1500 chars.
hashtags: 8-15 relevant, mix of broad and niche.

Topics that performed best recently (do more like these): {top_topics or 'none yet'}
Do NOT repeat any of these past topics: {past_topics[-80:] or 'none'}"""
    return llm.json_call(model, SYSTEM, prompt, POST_SCHEMA)


def _fake(page, fmt):
    return {
        "topic": f"Sample {fmt} for {page['id']}",
        "hook": "Did you know?",
        "slides": [{"heading": f"Fact {i}", "body": "Octopuses have three hearts and blue blood."} for i in range(1, 5)],
        "reel_script": ["Did you know octopuses have three hearts?", "Two pump blood to the gills.",
                        "One pumps it to the body.", "Follow for more!"],
        "caption": "Octopuses are wild 🐙\nSave this and share with a friend!",
        "hashtags": ["#funfacts", "#didyouknow", "#science"],
        "image_queries": ["octopus", "ocean", "coral reef", "underwater"],
        "sources": ["https://ocean.si.edu"],
        "contains_affiliate": False,
    }
