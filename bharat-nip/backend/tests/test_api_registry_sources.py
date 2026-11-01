from tests import scenario as sc

API = "/api/v1"


def test_registry_requires_rationale_and_audits_verification(api):
    admin = api.login(api.world.admin)
    r = api.post(
        f"{API}/registry",
        headers=admin,
        json={
            "name": "Example Election Commission",
            "domain": "https://www.elections.example.gov/",
            "category": "ELECTION_BODY",
            "jurisdiction": "RL",
            "authority_level": "PRIMARY_AUTHORITY",
        },
    )
    assert r.status_code == 422 and "rationale" in r.json()["detail"]
    r = api.post(
        f"{API}/registry",
        headers=admin,
        json={
            "name": "Example Election Commission",
            "domain": "https://www.elections.example.gov/",
            "category": "ELECTION_BODY",
            "jurisdiction": "RL",
            "authority_level": "PRIMARY_AUTHORITY",
            "authority_scope": ["election", "turnout"],
            "authority_rationale": "Constitutional body that conducts and certifies elections.",
            "default_source_type": "OFFICIAL_RECORD",
            "is_primary_source": True,
        },
    )
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["domain"] == "elections.example.gov"
    assert entry["verification_status"] == "UNVERIFIED"

    r = api.post(
        f"{API}/registry/{entry['id']}/verification",
        headers=admin,
        json={
            "status": "VERIFIED",
            "method": "Checked founding statute and site ownership.",
            "review_period_days": 180,
        },
    )
    assert r.json()["verification_status"] == "VERIFIED" and r.json()["review_due_at"]
    # A substantive edit invalidates the verification
    r = api.patch(
        f"{API}/registry/{entry['id']}", headers=admin, json={"authority_scope": ["election"]}
    )
    assert r.json()["verification_status"] == "UNVERIFIED"
    events = api.get(f"{API}/audit-events", headers=admin, params={"entity_id": entry["id"]}).json()
    assert [e["action"] for e in events] == [
        "registry.created",
        "registry.verification_set",
        "registry.updated",
    ]


def test_ingested_source_is_found_by_local_corpus_search(api, db_session):
    from app.providers.search.local_corpus import LocalCorpusSearchProvider

    analyst = api.login(api.world.submitter)
    body = {
        "title": "Annual Education Bulletin 2023",
        "url": sc.STATS_URL,
        "publisher_name": "Riverland Statistics Office",
        "source_type": "STATISTICAL_DATA",
        "published_at": "2024-01-15T00:00:00Z",
        "content_text": sc.STATS_TEXT,
    }
    r = api.post(f"{API}/sources", headers=analyst, json=body)
    assert r.status_code == 201 and r.json()["created"]
    src = r.json()["source"]
    assert src["is_primary"] and src["registry_source_id"]  # matched the registry domain
    again = api.post(f"{API}/sources", headers=analyst, json=body)
    assert again.status_code == 200 and not again.json()["created"]  # same content hash

    hits = LocalCorpusSearchProvider().search("Riverland literacy rate 2023", 5, session=db_session)
    assert hits and hits[0].source_id is not None and str(hits[0].source_id) == src["id"]
    assert hits[0].content == sc.STATS_TEXT
    full = api.get(f"{API}/sources/{src['id']}", headers=analyst).json()
    assert full["content_text"] == sc.STATS_TEXT
