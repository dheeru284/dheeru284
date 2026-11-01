"""Turn a submission into machine-readable text (pipeline stage CONTENT)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.core.hashing import sha256_text
from app.domain.enums import ActorType, ExtractionMethod, SubmissionStatus, SubmissionType
from app.ingest.extract import OCRUnavailable, extract_document, extract_pdf
from app.ingest.fetcher import FetchError
from app.models import StoredFile, Submission
from app.models.claims import MAX_EXTRACTED_CHARS
from app.pipeline.context import PipelineContext
from app.services.storage import read_stored


class ContentUnavailable(Exception):
    """No machine-readable text; a human transcription is needed."""


def _set(sub: Submission, text: str, method: ExtractionMethod, notes: str | None = None) -> None:
    truncated = len(text) > MAX_EXTRACTED_CHARS
    sub.extracted_text = text[:MAX_EXTRACTED_CHARS]
    sub.extraction_method = method
    sub.extraction_notes = (
        "; ".join(n for n in [notes, "truncated to 200,000 characters" if truncated else None] if n)
        or None
    )


def process_content(ctx: PipelineContext, submission: Submission) -> None:
    session: Session = ctx.session
    t = submission.submission_type
    if t == SubmissionType.TEXT:
        _set(submission, submission.raw_text or "", ExtractionMethod.USER_TEXT)
    elif t == SubmissionType.ARTICLE:
        header = "\n\n".join(x for x in [submission.title] if x)
        body = submission.raw_text or ""
        _set(submission, f"{header}\n\n{body}".strip(), ExtractionMethod.USER_TEXT)
    elif t == SubmissionType.VIDEO_METADATA:
        video = submission.metadata_.get("video", {})
        parts = [
            f"Video title: {video['title']}" if video.get("title") else None,
            f"Video description: {video['description']}" if video.get("description") else None,
            f"Transcript (supplied by submitter): {video['transcript']}"
            if video.get("transcript")
            else None,
        ]
        _set(
            submission,
            "\n\n".join(p for p in parts if p),
            ExtractionMethod.VIDEO_METADATA,
            "video not downloaded; metadata and submitter transcript only",
        )
    elif t == SubmissionType.URL:
        _process_url(ctx, submission)
    elif t in (SubmissionType.IMAGE, SubmissionType.PDF):
        _process_file(ctx, submission)

    status = (
        SubmissionStatus.PROCESSING
        if submission.extracted_text
        else SubmissionStatus.NEEDS_TRANSCRIPTION
    )
    submission.status = status
    session.flush()
    AuditService(session).record(
        actor_type=ActorType.SYSTEM,
        actor_id="system:content",
        action="submission.content_extracted"
        if submission.extracted_text
        else "submission.needs_transcription",
        entity_type="submission",
        entity_id=submission.id,
        payload={
            "method": submission.extraction_method.value if submission.extraction_method else None,
            "chars": len(submission.extracted_text or ""),
            "text_sha256": sha256_text(submission.extracted_text)
            if submission.extracted_text
            else None,
            "notes": submission.extraction_notes,
        },
    )
    if not submission.extracted_text:
        raise ContentUnavailable(submission.extraction_notes or "no machine-readable text")


def _process_url(ctx: PipelineContext, submission: Submission) -> None:
    assert submission.source_url
    try:
        doc = ctx.fetcher.fetch(submission.source_url)
    except FetchError as exc:
        # Fall back to text the submitter pasted, if any; otherwise the stage fails.
        if submission.raw_text:
            _set(
                submission,
                submission.raw_text,
                ExtractionMethod.USER_TEXT,
                f"URL fetch failed ({exc}); used submitter-provided text",
            )
            return
        raise
    extracted = extract_document(doc.content_type, doc.body)
    submission.metadata_ = {
        **submission.metadata_,
        "fetch": {
            "final_url": doc.final_url,
            "status_code": doc.status_code,
            "content_type": doc.content_type,
            "body_sha256": sha256_text(doc.body.decode("latin-1")),
            "fetched_at": doc.fetched_at.isoformat(),
            "redirects": doc.redirects,
        },
    }
    if extracted is None or not extracted.text:
        submission.extraction_notes = f"No extractable text at URL ({doc.content_type})."
        return
    submission.title = submission.title or extracted.title
    submission.publisher_name = submission.publisher_name or extracted.publisher
    submission.published_at = submission.published_at or extracted.published_at
    method = (
        ExtractionMethod.PDF_TEXT
        if doc.content_type == "application/pdf"
        else ExtractionMethod.HTML_EXTRACTION
    )
    _set(submission, extracted.text, method, f"fetched {doc.final_url}")


def _process_file(ctx: PipelineContext, submission: Submission) -> None:
    stored = ctx.session.get(StoredFile, submission.file_id)
    assert stored is not None
    data = read_stored(ctx.settings, stored)
    if submission.submission_type == SubmissionType.PDF:
        try:
            doc = extract_pdf(data)
        except ValueError as exc:
            submission.extraction_notes = str(exc)
            doc = None
        if doc is not None:
            submission.title = submission.title or doc.title
            _set(submission, doc.text, ExtractionMethod.PDF_TEXT)
            return
        reason = "PDF has no text layer (scanned)"
    else:
        reason = "image"
        if ctx.ocr.available:
            try:
                text = ctx.ocr.extract(data)
            except OCRUnavailable:
                text = None
            if text:
                _set(submission, text, ExtractionMethod.OCR, f"OCR by {ctx.ocr.name}")
                return
            reason = "OCR found no readable text"
        else:
            reason = "OCR is not installed on this server"
    if submission.raw_text and submission.raw_text.strip():
        _set(
            submission,
            submission.raw_text,
            ExtractionMethod.USER_TRANSCRIPTION,
            f"{reason}; used submitter transcription",
        )
    else:
        submission.extraction_notes = f"{reason}; a human transcription is required"
