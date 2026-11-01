import pytest

from app.ai.prompts import PromptRegistry
from app.ai.runs import AIRunRecorder
from app.core.hashing import sha256_json
from app.domain.enums import AIRunStatus
from app.models import AIRun
from app.providers.llm.base import ChatMessage, LLMRequest
from tests.test_prompts import PROMPT, write


@pytest.fixture
def prompt(tmp_path):
    write(tmp_path, "demo", "v1", PROMPT)
    return PromptRegistry(tmp_path).get("demo", "v1")


def make_request(prompt_id="demo"):
    return LLMRequest(prompt_id=prompt_id, messages=[ChatMessage(role="user", content="Claim: X")])


def test_successful_run_records_full_provenance(db_session, mock_llm, prompt):
    mock_llm.script("demo", '{"answer": 1}')
    request = make_request()
    response = mock_llm.complete(request)
    run = AIRunRecorder(db_session).record(
        agent_name="demo_agent",
        agent_version="1.0",
        prompt=prompt,
        provider=mock_llm,
        request=request,
        response=response,
        status=AIRunStatus.SUCCEEDED,
        output_parsed={"answer": 1},
    )
    stored = db_session.get(AIRun, run.id)
    assert stored.provider == "mock"
    assert stored.model == mock_llm.model
    assert stored.prompt_id == "demo"
    assert stored.prompt_version == "v1"
    assert stored.prompt_sha256 == prompt.sha256
    assert stored.input_sha256 == sha256_json([{"role": "user", "content": "Claim: X"}])
    assert stored.parameters["temperature"] == 0.0
    assert stored.output_parsed == {"answer": 1}


def test_failed_run_without_response_still_records_provider_identity(db_session, mock_llm, prompt):
    run = AIRunRecorder(db_session).record(
        agent_name="demo_agent",
        agent_version="1.0",
        prompt=prompt,
        provider=mock_llm,
        request=make_request(),
        response=None,
        status=AIRunStatus.FAILED,
        error="timeout",
    )
    assert run.provider == "mock"
    assert run.model == mock_llm.model
    assert run.output_text is None
    assert run.error == "timeout"


def test_prompt_mismatch_is_refused(db_session, mock_llm, prompt):
    with pytest.raises(ValueError, match="prompt_id"):
        AIRunRecorder(db_session).record(
            agent_name="demo_agent",
            agent_version="1.0",
            prompt=prompt,
            provider=mock_llm,
            request=make_request(prompt_id="other"),
            response=None,
            status=AIRunStatus.FAILED,
        )


def test_success_requires_response(db_session, mock_llm, prompt):
    with pytest.raises(ValueError, match="SUCCEEDED"):
        AIRunRecorder(db_session).record(
            agent_name="demo_agent",
            agent_version="1.0",
            prompt=prompt,
            provider=mock_llm,
            request=make_request(),
            response=None,
            status=AIRunStatus.SUCCEEDED,
        )
