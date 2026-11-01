"""Speaker independence (PRODUCT_REQUIREMENTS.md rule 1): the same claim made by people
from opposing parties must reach the assessor as byte-identical input and get the same
classification. All names are fictional."""

import pytest
from sqlalchemy import select

from app.domain.enums import EntityType, SubmissionType
from app.domain.text import blind
from app.models import AIRun, Assessment, Claim, Entity
from app.pipeline import orchestrator
from app.services.submissions import SubmissionInput, create_submission
from tests import scenario as sc

SPEAKERS = [
    ("Asha Verma", "Riverland People's Front"),
    ("Ravi Menon", "Riverland Progress Party"),
    ("Dr. K. Iyer", "Riverland Unity Alliance"),
]


def test_assessor_input_and_classification_do_not_depend_on_speaker(db_session, settings):
    world = sc.make_world(db_session)
    world.search.script([sc.stats_hit(), sc.news_hit()])
    world.llm.script("evidence_analyst", sc.evidence_response, reusable=True)
    world.llm.script("assessor", sc.assessment_response(), reusable=True)
    world.llm.script("fact_check_critic", sc.critic_response("PASS"), reusable=True)
    ctx = sc.make_context(db_session, settings, world)

    results = []
    for name, party in SPEAKERS:
        speaker = Entity(name=name, entity_type=EntityType.PERSON, description=party)
        db_session.add(speaker)
        db_session.flush()
        world.llm.script("claim_extractor", sc.extraction_response(speaker=name))
        sub, _ = create_submission(
            db_session,
            world.submitter,
            SubmissionInput(
                submission_type=SubmissionType.TEXT,
                raw_text=f'{name} ({party}) said: "{sc.CLAIM_SENTENCE}"',
                speaker_entity_id=speaker.id,
            ),
        )
        [claim_id] = orchestrator.process_submission(ctx, sub.id)
        claim = db_session.get(Claim, claim_id)
        assessment = db_session.scalar(select(Assessment).where(Assessment.claim_id == claim.id))
        run = db_session.get(AIRun, assessment.ai_run_id)
        results.append((claim.normalized_text, run.input_sha256, assessment.classification))

    normalized, input_hashes, classifications = zip(*results, strict=True)
    assert len(set(normalized)) == 1, normalized
    assert len(set(input_hashes)) == 1, "assessor input differed by speaker"
    assert len(set(classifications)) == 1
    for call in world.llm.calls_for("assessor"):
        text = " ".join(m.content for m in call.messages)
        for name, party in SPEAKERS:
            assert name not in text and party not in text


@pytest.mark.parametrize(
    ("text", "names", "expected"),
    [
        ("Asha Verma said X.", ["Asha Verma"], "[SPEAKER] said X."),
        ("asha verma's plan", ["Asha Verma"], "[SPEAKER] plan"),
        (
            "Minister Asha Verma and Asha",
            ["Asha Verma", "Minister Asha Verma"],
            "[SPEAKER] and Asha",
        ),
        ("Vermaville is a town", ["Verma"], "Vermaville is a town"),  # whole words only
    ],
)
def test_blinding(text, names, expected):
    assert blind(text, names) == expected
