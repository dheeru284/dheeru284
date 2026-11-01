import json

import httpx

from app.ingest.fetcher import SafeFetcher
from tests import scenario as sc
from tests.helpers import PNG_1X1, make_text_pdf

API = "/api/v1"


def _claim_ids(api, headers, submission_id):
    detail = api.get(f"{API}/submissions/{submission_id}", headers=headers).json()
    return detail, [c["id"] for c in detail["claims"]]


def _script_minimal(world):
    world.llm.script("claim_extractor", sc.extraction_response(), reusable=True)
    world.search.script([])


def test_auth_required_and_bad_password(api):
    assert api.get(f"{API}/claims").status_code == 401
    r = api.post(f"{API}/auth/token", json={"email": api.world.reviewer.email, "password": "no"})
    assert r.status_code == 401
    me = api.get(f"{API}/auth/me", headers=api.login(api.world.reviewer)).json()
    assert me["role"] == "REVIEWER"


def test_role_checks(api):
    analyst = api.login(api.world.submitter)
    assert api.get(f"{API}/review-tasks", headers=analyst).status_code == 403
    assert api.get(f"{API}/audit-events/verify", headers=analyst).status_code == 403
    assert api.post(f"{API}/registry", json={}, headers=analyst).status_code in (403, 422)


def test_validation_errors_are_problem_json(api):
    r = api.post(
        f"{API}/submissions",
        json={"submission_type": "URL"},
        headers=api.login(api.world.submitter),
    )
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")


def test_url_submission_is_fetched_and_extracted(api):
    _script_minimal(api.world)
    html = (
        "<html><head><meta property='og:site_name' content='Example Daily'></head><body>"
        f"<article><p>{sc.SUBMISSION_TEXT}</p></article></body></html>"
    )
    api.ctx.fetcher = SafeFetcher(
        api.ctx.settings,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=html, headers={"content-type": "text/html"})
        ),
        resolver=lambda host: ["93.184.216.34"],
    )
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions",
        headers=h,
        json={"submission_type": "URL", "source_url": "https://daily.example.com/a"},
    )
    detail, ids = _claim_ids(api, h, r.json()["submission"]["id"])
    sub = detail["submission"]
    assert sub["extraction_method"] == "HTML_EXTRACTION"
    assert sub["publisher_name"] == "Example Daily"
    assert sub["metadata"]["fetch"]["status_code"] == 200
    assert len(ids) == 1
    claim = api.get(f"{API}/claims/{ids[0]}", headers=h).json()["claim"]
    assert claim["original_source"]["url"] == "https://daily.example.com/a"


def test_url_to_private_network_is_refused(api):
    api.ctx.fetcher = SafeFetcher(api.ctx.settings, resolver=lambda host: ["10.1.2.3"])
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions",
        headers=h,
        json={"submission_type": "URL", "source_url": "https://internal.example.com/"},
    )
    detail, ids = _claim_ids(api, h, r.json()["submission"]["id"])
    assert detail["submission"]["status"] == "FAILED"
    assert "non-public" in detail["submission"]["extraction_notes"]
    assert ids == []


def test_article_submission(api):
    _script_minimal(api.world)
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions",
        headers=h,
        json={
            "submission_type": "ARTICLE",
            "title": "Rally report",
            "publisher_name": "Example News",
            "raw_text": sc.SUBMISSION_TEXT,
        },
    )
    detail, ids = _claim_ids(api, h, r.json()["submission"]["id"])
    assert detail["submission"]["extraction_method"] == "USER_TEXT" and len(ids) == 1


def test_pdf_upload(api):
    _script_minimal(api.world)
    h = api.login(api.world.submitter)
    pdf = make_text_pdf([sc.SUBMISSION_TEXT[:90], sc.SUBMISSION_TEXT[90:]])
    r = api.post(
        f"{API}/submissions/upload",
        headers=h,
        files={"file": ("speech.pdf", pdf, "application/pdf")},
        data={"payload": json.dumps({"submission_type": "PDF"})},
    )
    assert r.status_code == 201, r.text
    detail, ids = _claim_ids(api, h, r.json()["submission"]["id"])
    assert detail["submission"]["extraction_method"] == "PDF_TEXT" and len(ids) == 1


def test_image_without_ocr_needs_human_transcription(api):
    _script_minimal(api.world)
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions/upload",
        headers=h,
        files={"file": ("poster.png", PNG_1X1, "image/png")},
        data={"payload": json.dumps({"submission_type": "IMAGE"})},
    )
    sid = r.json()["submission"]["id"]
    detail, ids = _claim_ids(api, h, sid)
    assert detail["submission"]["status"] == "NEEDS_TRANSCRIPTION" and ids == []
    assert "transcription is required" in detail["submission"]["extraction_notes"]

    r = api.post(
        f"{API}/submissions/{sid}/transcription", headers=h, json={"text": sc.SUBMISSION_TEXT}
    )
    assert r.status_code == 200, r.text
    detail, ids = _claim_ids(api, h, sid)
    assert detail["submission"]["extraction_method"] == "USER_TRANSCRIPTION" and len(ids) == 1


def test_upload_type_is_sniffed_not_trusted(api):
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions/upload",
        headers=h,
        files={"file": ("evil.pdf", b"#!/bin/sh\necho hi", "application/pdf")},
        data={"payload": json.dumps({"submission_type": "PDF"})},
    )
    assert r.status_code == 422
    r = api.post(
        f"{API}/submissions/upload",
        headers=h,
        files={"file": ("p.png", PNG_1X1, "image/png")},
        data={"payload": json.dumps({"submission_type": "PDF"})},
    )
    assert r.status_code == 422 and "does not match" in r.json()["detail"]


def test_video_metadata_submission(api):
    _script_minimal(api.world)
    h = api.login(api.world.submitter)
    r = api.post(
        f"{API}/submissions",
        headers=h,
        json={
            "submission_type": "VIDEO_METADATA",
            "video": {
                "platform": "ExampleTube",
                "video_url": "https://video.example.com/v/1",
                "title": "Rally speech",
                "transcript": sc.SUBMISSION_TEXT,
            },
        },
    )
    detail, ids = _claim_ids(api, h, r.json()["submission"]["id"])
    assert detail["submission"]["extraction_method"] == "VIDEO_METADATA"
    assert "not downloaded" in detail["submission"]["extraction_notes"]
    assert len(ids) == 1
    bad = api.post(
        f"{API}/submissions",
        headers=h,
        json={"submission_type": "VIDEO_METADATA", "video": {"platform": "X"}},
    )
    assert bad.status_code == 422


def test_submitter_sees_only_own_and_only_approved_results(api, db_session):
    from app.domain.enums import UserRole
    from app.services.users import create_user

    _script_minimal(api.world)
    outsider = create_user(
        db_session,
        email="o@test.example",
        display_name="O",
        role=UserRole.SUBMITTER,
        password=sc.PASSWORD,
        created_by=None,
    )
    owner = create_user(
        db_session,
        email="s@test.example",
        display_name="S",
        role=UserRole.SUBMITTER,
        password=sc.PASSWORD,
        created_by=None,
    )
    h_owner, h_out = api.login(owner), api.login(outsider)
    sid = api.post(
        f"{API}/submissions",
        headers=h_owner,
        json={"submission_type": "TEXT", "raw_text": sc.SUBMISSION_TEXT},
    ).json()["submission"]["id"]
    _, [cid] = _claim_ids(api, h_owner, sid)
    assert api.get(f"{API}/submissions/{sid}", headers=h_out).status_code == 404
    assert api.get(f"{API}/claims/{cid}", headers=h_out).status_code == 404
    assert api.get(f"{API}/claims", headers=h_out).json()["items"] == []
    # owner sees the claim but not the unreviewed result
    assert api.get(f"{API}/claims/{cid}", headers=h_owner).status_code == 200
    assert api.get(f"{API}/claims/{cid}/fact-check", headers=h_owner).status_code == 403
