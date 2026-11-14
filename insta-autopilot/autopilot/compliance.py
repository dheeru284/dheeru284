"""Policy gate: hard keyword rules + an independent Claude review. Anything doubtful is rejected."""
import re

from . import llm

BLOCK_PATTERNS = [
    r"guaranteed (returns|profit|income)", r"double your money", r"\bstock tip", r"buy (this|these) shares",
    r"\bcure[sd]?\b.*(cancer|diabetes|covid)", r"\bbetting\b", r"\bcasino\b", r"\bsatta\b",
    r"\bvote for\b", r"\bfollow ?for ?follow\b", r"\bf4f\b", r"\bl4l\b",
]

REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["approved", "issues", "needs_paid_label"],
    "properties": {
        "approved": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "needs_paid_label": {"type": "boolean"},
    },
}

REVIEW_SYSTEM = """You are a strict content-policy reviewer for Instagram pages operating in India.
Reject (approved=false) if the post: violates Instagram Community Guidelines; could hurt religious or communal
sentiment; contains hate, harassment, sexual content, violence glorification or dangerous challenges; gives medical,
legal or investment advice or misleading financial claims (SEBI); makes unverifiable or likely false factual claims;
copies copyrighted text/characters; is political campaigning; or is engagement bait (follow-for-follow, fake giveaways).
needs_paid_label=true if it promotes a product, brand or affiliate link (ASCI guidelines)."""


def check(post, model):
    text = " ".join([post["caption"], " ".join(post["hashtags"]),
                     " ".join(s["heading"] + " " + s["body"] for s in post["slides"]),
                     " ".join(post["reel_script"])])
    hits = [p for p in BLOCK_PATTERNS if re.search(p, text, re.I)]
    if hits:
        return {"approved": False, "issues": [f"blocked pattern: {h}" for h in hits], "needs_paid_label": False}
    if llm.fake_enabled():
        return {"approved": True, "issues": [], "needs_paid_label": post["contains_affiliate"]}
    try:
        return llm.json_call(model, REVIEW_SYSTEM, "Review this post JSON:\n" + str(post), REVIEW_SCHEMA,
                             max_tokens=4000, effort="low")
    except llm.Refused as e:
        return {"approved": False, "issues": [f"reviewer refused: {e}"], "needs_paid_label": False}


def finalize_caption(post, review):
    """Add required disclosures to the caption."""
    caption = post["caption"].strip()
    if review["needs_paid_label"] or post["contains_affiliate"]:
        caption = "#ad (affiliate links, I may earn a commission)\n" + caption
    caption += "\n\n" + " ".join(post["hashtags"][:15])
    return caption[:2200]
