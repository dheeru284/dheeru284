"""CLI: python -m autopilot.main {generate|publish|insights} [--dry-run] [--page ID]"""
import argparse
import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

import yaml

from . import compliance, content, render
from .instagram import IG

ROOT = Path(__file__).resolve().parent.parent
QUEUE, STATE = ROOT / "queue", ROOT / "state"


def load_config():
    return yaml.safe_load((ROOT / "config/pages.yaml").read_text())


def secret(name):
    if name in os.environ:
        return os.environ[name]
    blob = os.environ.get("SECRETS_JSON")
    return json.loads(blob).get(name) if blob else None


def creds(page):
    pid = page["id"].upper()
    return secret(f"IG_{pid}_USER_ID"), secret(f"IG_{pid}_TOKEN")


def state(page_id):
    p = STATE / f"{page_id}.json"
    return json.loads(p.read_text()) if p.exists() else {"topics": [], "top_topics": [], "followers": []}


def save_state(page_id, s):
    STATE.mkdir(exist_ok=True)
    (STATE / f"{page_id}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))


def ist_to_utc(day, hhmm, offset_min):
    h, m = map(int, hhmm.split(":"))
    local = dt.datetime.combine(day, dt.time(h, m))
    return (local - dt.timedelta(minutes=offset_min)).replace(tzinfo=dt.timezone.utc)


def cmd_generate(cfg, args):
    s = cfg["settings"]
    today = dt.date.today() + dt.timedelta(days=1)  # generate for tomorrow so there is time to approve
    made = 0
    for page in cfg["pages"]:
        if not page.get("enabled") or (args.page and page["id"] != args.page):
            continue
        uid, tok = creds(page)
        if not (uid and tok) and not args.dry_run:
            print(f"[skip] {page['id']}: no IG credentials yet")
            continue
        if page["id"] == "aiinfluencer" and not any(Path(ROOT, page["character_assets_dir"]).glob("*.*")):
            print("[skip] aiinfluencer: add character images to", page["character_assets_dir"])
            continue
        page = {**page, "character_assets_dir": str(ROOT / page["character_assets_dir"])
                if page.get("character_assets_dir") else None}
        st = state(page["id"])
        slots = [f for f, n in page["formats"].items() for _ in range(n)]
        for i, fmt in enumerate(slots):
            out = QUEUE / today.isoformat() / page["id"] / f"{fmt}{i}"
            if (out / "post.json").exists():
                continue
            try:
                post = content.generate(page, fmt, s["model"], st["topics"], st["top_topics"])
                review = compliance.check(post, s["model"])
                if not review["approved"]:
                    print(f"[rejected] {page['id']} {fmt}: {review['issues']}")
                    continue
                out.mkdir(parents=True, exist_ok=True)
                seed = f"{page['id']}-{today}-{i}"
                if fmt == "carousel":
                    media = [p.relative_to(ROOT).as_posix() for p in render.carousel(post, page, out, seed)]
                else:
                    v, c = render.reel(post, page, out, seed)
                    media = [v.relative_to(ROOT).as_posix(), c.relative_to(ROOT).as_posix()]
                caption = compliance.finalize_caption(post, review)
                if page["id"] == "aiinfluencer":
                    caption = "✨ AI-generated virtual creator\n" + caption
                times = page["post_times"]
                when = ist_to_utc(today, times[i % len(times)], s["timezone_offset_minutes"])
                (out / "post.json").write_text(json.dumps({
                    "page": page["id"], "format": fmt, "scheduled_at": when.isoformat(),
                    "caption": caption, "media": media, "topic": post["topic"],
                    "sources": post["sources"], "review": review, "published": None,
                }, ensure_ascii=False, indent=1))
                st["topics"].append(post["topic"])
                made += 1
                print(f"[ok] {page['id']} {fmt}: {post['topic']}")
            except Exception:
                traceback.print_exc()
        save_state(page["id"], st)
    print(f"generated {made} posts for {today}")


def public_url(rel):
    repo = os.environ.get("GITHUB_REPOSITORY")
    branch = os.environ.get("MEDIA_BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/insta-autopilot/{rel}"


def cmd_publish(cfg, args):
    now = dt.datetime.now(dt.timezone.utc)
    pages = {p["id"]: p for p in cfg["pages"]}
    for pj in sorted(QUEUE.glob("*/*/*/post.json")):
        post = json.loads(pj.read_text())
        if post["published"] or dt.datetime.fromisoformat(post["scheduled_at"]) > now:
            continue
        page = pages.get(post["page"])
        uid, tok = creds(page)
        if not (uid and tok):
            continue
        if args.dry_run:
            print("[dry-run] would publish", pj)
            continue
        ig = IG(uid, tok, cfg["settings"]["graph_api_version"])
        try:
            if post["format"] == "carousel":
                mid = ig.publish_carousel([public_url(m) for m in post["media"]], post["caption"])
            else:
                mid = ig.publish_reel(public_url(post["media"][0]), public_url(post["media"][1]), post["caption"])
            post["published"] = {"media_id": mid, "at": now.isoformat()}
            print(f"[published] {pj.parent} -> {mid}")
        except Exception as e:
            post.setdefault("errors", []).append(f"{now.isoformat()} {e}"[:500])
            print(f"[error] {pj.parent}: {e}")
        pj.write_text(json.dumps(post, ensure_ascii=False, indent=1))


def cmd_insights(cfg, args):
    report = ["# Weekly performance\n"]
    for page in cfg["pages"]:
        uid, tok = creds(page)
        if not (uid and tok):
            continue
        ig = IG(uid, tok, cfg["settings"]["graph_api_version"])
        st = state(page["id"])
        info = ig.followers()
        st["followers"].append({"date": dt.date.today().isoformat(), "count": info.get("followers_count")})
        topic_by_id = {}
        for pj in QUEUE.glob(f"*/{page['id']}/*/post.json"):
            p = json.loads(pj.read_text())
            if p.get("published"):
                topic_by_id[p["published"]["media_id"]] = p["topic"]
        scored = []
        for m in ig.recent_media(50):
            ins = ig.insights(m["id"])
            score = ins.get("shares", 0) * 3 + ins.get("saved", 0) * 2 + ins.get("total_interactions", 0) \
                + ins.get("reach", 0) / 100 if "error" not in ins else 0
            scored.append((score, topic_by_id.get(m["id"], (m.get("caption") or "")[:80])))
        scored.sort(reverse=True)
        st["top_topics"] = [t for _, t in scored[:8]]
        save_state(page["id"], st)
        report.append(f"## {page['id']} ({page['handle']}): {info.get('followers_count')} followers\n")
        report += [f"- {sc:.0f}  {t}" for sc, t in scored[:5]] + [""]
    (STATE / "REPORT.md").write_text("\n".join(report))
    print("\n".join(report))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["generate", "publish", "insights"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--page")
    args = ap.parse_args()
    cfg = load_config()
    {"generate": cmd_generate, "publish": cmd_publish, "insights": cmd_insights}[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
