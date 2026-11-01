"""Turn fetched or uploaded material into plain text, recording how it was obtained.

Nothing here invents text: when no machine-readable text exists (e.g. an image without
OCR, a scanned PDF), the result says so and the submission needs a human transcription.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MIN_TEXT_CHARS = 20
_WS = re.compile(r"[ \t\r\f\v]+")
_BLANKS = re.compile(r"\n{3,}")

PDF_MAGIC = b"%PDF-"
IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
}


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    title: str | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    language: str | None = None


def normalize_text(text: str) -> str:
    lines = [_WS.sub(" ", line).strip() for line in text.splitlines()]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def sniff_content_type(data: bytes) -> str | None:
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    for magic, ctype in IMAGE_MAGIC.items():
        if data.startswith(magic):
            return ctype
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _meta(soup: BeautifulSoup, *keys: str) -> str | None:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    return None


def extract_html(html: str) -> ExtractedDocument:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title", "twitter:title") or (
        soup.title.get_text(strip=True) if soup.title else None
    )
    publisher = _meta(soup, "og:site_name", "publisher", "author")
    published = _parse_date(
        _meta(soup, "article:published_time", "datePublished", "pubdate", "date")
    )
    if published is None:
        time_tag = soup.find("time", attrs={"datetime": True})
        published = _parse_date(time_tag["datetime"]) if time_tag else None
    language = (soup.html.get("lang") if soup.html else None) or None

    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks = [
        el.get_text(" ", strip=True)
        for el in root.find_all(["h1", "h2", "h3", "p", "li", "blockquote", "td"])
    ]
    text = "\n\n".join(b for b in blocks if b)
    if len(text) < MIN_TEXT_CHARS:
        text = root.get_text("\n", strip=True)
    return ExtractedDocument(
        text=normalize_text(text),
        title=title,
        publisher=publisher,
        published_at=published,
        language=str(language)[:10] if language else None,
    )


def extract_pdf(data: bytes) -> ExtractedDocument | None:
    """Text layer of a PDF, or None when it has none (scanned)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        meta = reader.metadata
    except (PdfReadError, ValueError, OSError) as exc:
        raise ValueError(f"Unreadable PDF: {exc}") from exc
    text = normalize_text("\n\n".join(pages))
    if len(text.replace(" ", "")) < MIN_TEXT_CHARS:
        return None
    title = str(meta.title).strip() if meta and meta.title else None
    return ExtractedDocument(text=text, title=title)


def extract_document(content_type: str, body: bytes) -> ExtractedDocument | None:
    """Dispatch on content type for fetched documents."""
    if content_type == "application/pdf" or body.startswith(PDF_MAGIC):
        return extract_pdf(body)
    if content_type in ("text/html", "application/xhtml+xml") or not content_type:
        return extract_html(body.decode("utf-8", errors="replace"))
    if content_type.startswith("text/"):
        return ExtractedDocument(text=normalize_text(body.decode("utf-8", errors="replace")))
    return None


class OCRUnavailable(Exception):
    pass


class TesseractOCR:
    """OCR via the local `tesseract` binary, if installed. Free and offline."""

    name = "tesseract"

    def __init__(self, binary: str | None = None) -> None:
        self.binary = binary or shutil.which("tesseract")

    @property
    def available(self) -> bool:
        return self.binary is not None

    def extract(self, image: bytes) -> str | None:
        if not self.binary:
            raise OCRUnavailable("tesseract is not installed")
        proc = subprocess.run(
            [self.binary, "stdin", "stdout"],
            input=image,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            return None
        text = normalize_text(proc.stdout.decode("utf-8", errors="replace"))
        return text if len(text) >= MIN_TEXT_CHARS else None
