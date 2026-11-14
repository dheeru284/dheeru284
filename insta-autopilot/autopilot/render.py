"""Render carousels (1080x1350 JPG) and Reels (1080x1920 MP4 with TTS voiceover + Ken Burns motion)."""
import asyncio
import io
import os
import random
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_FAMILY = {"Hindi": "Noto Sans Devanagari", "Telugu": "Noto Sans Telugu"}
PALETTES = [((20, 30, 70), (120, 40, 140)), ((10, 60, 60), (20, 140, 110)),
            ((70, 20, 20), (200, 90, 40)), ((15, 15, 15), (60, 60, 90))]


def _font(language, size, bold=True):
    family = FONT_FAMILY.get(language, "Noto Sans")
    style = ":bold" if bold else ""
    try:
        path = subprocess.run(["fc-match", "-f", "%{file}", f"{family}{style}"],
                              capture_output=True, text=True, check=True).stdout.strip()
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.load_default(size)


def _background(size, query, page, rng):
    w, h = size
    img = None
    assets = page.get("character_assets_dir")
    if assets and Path(assets).is_dir():
        files = sorted(p for p in Path(assets).iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        if files:
            img = Image.open(rng.choice(files)).convert("RGB")
    key = os.environ.get("PEXELS_API_KEY")
    if img is None and key and query:
        try:
            r = requests.get("https://api.pexels.com/v1/search", headers={"Authorization": key},
                             params={"query": query, "per_page": 10,
                                     "orientation": "portrait"}, timeout=20)
            photos = r.json().get("photos", [])
            if photos:
                url = rng.choice(photos)["src"]["large2x"]
                img = Image.open(io.BytesIO(requests.get(url, timeout=30).content)).convert("RGB")
        except Exception as e:
            print("pexels failed:", e)
    if img is None:
        a, b = rng.choice(PALETTES)
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / h
            d.line([(0, y), (w, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
        return img
    # cover-crop
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _wrap(draw, text, font, max_w):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _slide(size, heading, body, idx, total, page, query, rng, handle):
    w, h = size
    img = _background(size, query, page, rng)
    # darken for legibility
    shade = Image.new("RGB", size, (0, 0, 0))
    img = Image.blend(img, shade, 0.45).filter(ImageFilter.GaussianBlur(0.5))
    d = ImageDraw.Draw(img)
    lang = page["language"]
    hf, bf, sf = _font(lang, 78), _font(lang, 50, bold=False), _font("English", 34, bold=False)
    margin = 90
    hl = _wrap(d, heading, hf, w - 2 * margin)
    bl = _wrap(d, body, bf, w - 2 * margin)
    block = len(hl) * 105 + 40 + len(bl) * 72
    y = (h - block) // 2
    for line in hl:
        d.text((margin, y), line, font=hf, fill=(255, 214, 80))
        y += 105
    y += 40
    for line in bl:
        d.text((margin, y), line, font=bf, fill=(255, 255, 255))
        y += 72
    d.text((margin, h - 110), handle, font=sf, fill=(220, 220, 220))
    d.text((w - margin - 90, h - 110), f"{idx}/{total}", font=sf, fill=(220, 220, 220))
    return img


def carousel(post, page, out_dir, seed):
    rng = random.Random(seed)
    slides = post["slides"][:10]
    paths = []
    for i, s in enumerate(slides, 1):
        q = post["image_queries"][(i - 1) % max(1, len(post["image_queries"]))] if post["image_queries"] else ""
        img = _slide((1080, 1350), s["heading"], s["body"], i, len(slides), page, q, rng, page["handle"])
        p = out_dir / f"slide{i:02d}.jpg"
        img.save(p, quality=90)
        paths.append(p)
    return paths


async def _tts(text, voice, path):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(str(path))


def _duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def reel(post, page, out_dir, seed):
    rng = random.Random(seed)
    slides = post["slides"][:8]
    script = post["reel_script"]
    segs = []
    for i, s in enumerate(slides, 1):
        q = post["image_queries"][(i - 1) % max(1, len(post["image_queries"]))] if post["image_queries"] else ""
        frame = out_dir / f"frame{i:02d}.jpg"
        _slide((1080, 1920), s["heading"], s["body"], i, len(slides), page, q, rng, page["handle"]).save(frame, quality=92)
        audio = out_dir / f"vo{i:02d}.mp3"
        line = script[i - 1] if i - 1 < len(script) else s["body"]
        try:
            asyncio.run(_tts(line, page["voice"], audio))
        except Exception as e:  # keep the pipeline alive; reel gets silent segment
            print("TTS failed, using silence:", e)
            secs = max(2.5, len(line.split()) * 0.45)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                            "anullsrc=r=44100:cl=stereo", "-t", f"{secs:.1f}", str(audio)], check=True)
        dur = _duration(audio) + 0.4
        frames = int(dur * 30)
        seg = out_dir / f"seg{i:02d}.mp4"
        zoom = "zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'" \
               f":d={frames}:s=1080x1920:fps=30"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(frame), "-i", str(audio),
                        "-vf", zoom, "-t", f"{dur:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-af", "apad", "-shortest", str(seg)], check=True)
        segs.append(seg)
    lst = out_dir / "segments.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs))
    final = out_dir / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart", str(final)],
                   check=True)
    cover = out_dir / "cover.jpg"
    (out_dir / "frame01.jpg").replace(cover)
    for p in list(out_dir.glob("frame*.jpg")) + list(out_dir.glob("vo*.mp3")) + segs + [lst]:
        p.unlink(missing_ok=True)
    return final, cover
