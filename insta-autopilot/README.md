# Insta Autopilot

This automates 7 Instagram pages (fun facts, economy stories, Hindi itihaas, tech & AI, Telugu travel, Telugu cooking, and an AI influencer). It runs entirely on GitHub Actions and posts only through Meta's official Graph API.

```
daily 08:47 IST  generate ─▶ Claude writes post ─▶ policy gate (rules + Claude review) ─▶ render
                                   ▲                                                      │ carousel JPGs / Reel MP4 + voiceover
                                   │ top topics                                           ▼
weekly          insights ◀──── Graph API insights                   PR for approval (first 2 weeks) / main
every 30 min    publish  ─────────────────────────────────▶ Graph API: carousel / Reel at the scheduled IST time
```

**Setup:** follow [SETUP.md](SETUP.md).

**Run locally without an API key:**
```bash
cd insta-autopilot && pip install -r requirements.txt
AUTOPILOT_FAKE_LLM=1 python -m autopilot.main generate --dry-run --page funfacts
```

## What it will NOT do (these get accounts banned)
- Create accounts with bots
- Buy followers or run follow/unfollow or engagement-pod schemes
- Send automated DMs or comments
- Repost other creators' content or use copyrighted music

Growth comes only from consistent, original posts that people save and share.

## Policy safeguards (India)
- Every post passes a hard keyword block and an independent Claude review. The review checks Instagram Community Guidelines, IT Rules 2021, communal or religious sensitivity, and SEBI rules (no investment advice).
- Affiliate or brand posts automatically get an `#ad` disclosure, as ASCI guidelines require.
- AI influencer posts are labelled as an AI-generated virtual creator. Also turn on Instagram's **"AI info"** label when you review the first posts.
- Every post stores its sources in `post.json`, so you can check facts.

## Monetization roadmap
| Followers | What to switch on |
|---|---|
| 0+ | Amazon Associates India / EarnKaro affiliate links. Put your tag in `affiliate_tag` and link-in-bio (Linktree or a free GitHub Pages page). |
| 1K+ | Instagram Subscriptions and Gifts, if eligible. Your own ₹99–₹499 digital products: e-book of money stories, Telugu recipe PDF, AI-prompt pack. |
| 10K+ | Brand deals. List each page on creator marketplaces (Instagram Creator Marketplace, Winkl, Plixxo). Usually ₹2K–₹20K per post at 10–100K followers. |
| 50K+ | Sell shout-outs across your own pages and run sponsored series. The AI influencer can take brand ambassador deals. |

The best payers for these niches are tech/AI tool sponsorships (techai, aiinfluencer) and finance education sponsors (econstories, with no stock tips).

## Upgrade path
Right now Reels are image slides with Ken Burns motion and a neural voiceover (free). For animated "economy story" Reels, plug in Higgsfield video generation per slide. That costs about ₹50–150 per Reel in credits.
