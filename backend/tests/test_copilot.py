"""Copilot behaviour: real model calls, persistence, and honest failure.

The central regression these guard against is the previous implementation
silently substituting a string-template "executive summary" whenever the model
was unreachable, so a Copilot with no API key looked like it was working.
"""

import json

import pytest

from app.services.llm import LLMQuotaExceeded, LLMRateLimited, LLMTimeout


def ask(client, account, query="Why is Pump P-101 overheating?", **kwargs):
    payload = {"query": query, **kwargs}
    return client.post("/api/v1/chat/ask", json=payload, headers=account.headers())


def test_uncited_model_answer_is_not_presented_as_evidence(client, alice, stub_llm):
    stub_llm.structured_response = {
        "executive_summary": "A distinctive answer only the model could produce.",
        "root_cause": "Bearing degradation.",
        "supporting_evidence": ["Log entry 42."],
        "recommended_action": "Replace the bearing.",
        "business_impact": "Two hours of downtime.",
        "risk_level": "High",
        "confidence": 0.9,
    }
    response = ask(client, alice)
    assert response.status_code == 200

    decision = response.json()["data"]["decision"]
    assert decision["executive_summary"] != "A distinctive answer only the model could produce."
    assert decision["evidence_status"] == "insufficient"
    assert decision["citations"] == []
    assert stub_llm.call_count == 1


def test_no_model_configured_returns_an_error_not_a_fabricated_answer(client, alice):
    """With LLM_PROVIDER=null the Copilot must fail loudly."""
    response = ask(client, alice)
    assert response.status_code == 503
    message = response.json()["error"]["message"]
    assert "not configured" in message.lower() or "unavailable" in message.lower()


@pytest.mark.parametrize(
    "error", [LLMTimeout("timeout"), LLMRateLimited("429"), LLMQuotaExceeded("quota")]
)
def test_model_failures_surface_as_retryable_errors(client, alice, stub_llm, error):
    stub_llm.raise_error = error
    response = ask(client, alice)
    assert response.status_code == 503
    body = response.json()
    assert body["success"] is False
    # The user-facing message must not leak provider internals.
    assert "429" not in body["error"]["message"]
    assert "Traceback" not in body["error"]["message"]


def test_malformed_model_output_does_not_crash_the_request(client, alice, stub_llm):
    from app.services.llm import LLMInvalidResponse

    stub_llm.raise_error = LLMInvalidResponse("not json")
    response = ask(client, alice)
    assert response.status_code == 503
    assert response.json()["success"] is False


def test_conversation_and_messages_are_persisted(client, alice, stub_llm):
    """History must survive a refresh; it used to live only in React state."""
    first = ask(client, alice, query="Why is Pump P-101 overheating?")
    assert first.status_code == 200
    conversation_id = first.json()["data"]["conversation_id"]

    listing = client.get("/api/v1/chat/conversations", headers=alice.headers())
    assert listing.status_code == 200
    assert listing.json()["data"]["total_items"] == 1

    detail = client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice.headers()
    )
    assert detail.status_code == 200
    messages = detail.json()["data"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "Why is Pump P-101 overheating?"
    assert messages[1]["payload"]["decision"]["risk_level"] in {None, "Low", "Medium", "High", "Critical"}


def test_follow_up_appends_to_the_same_conversation(client, alice, stub_llm):
    first = ask(client, alice, query="What is Pump P-101?")
    conversation_id = first.json()["data"]["conversation_id"]

    second = ask(client, alice, query="And why did it fail?", conversation_id=conversation_id)
    assert second.json()["data"]["conversation_id"] == conversation_id

    detail = client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=alice.headers()
    ).json()["data"]
    assert len(detail["messages"]) == 4


def test_prior_turns_are_sent_to_the_model_for_follow_ups(client, alice, stub_llm):
    first = ask(client, alice, query="Tell me about Pump P-101.")
    conversation_id = first.json()["data"]["conversation_id"]

    ask(client, alice, query="Why did it fail?", conversation_id=conversation_id)

    # The second prompt must carry the first turn, or "it" is unresolvable.
    assert "Tell me about Pump P-101." in stub_llm.prompts[-1]


def test_the_question_is_saved_even_when_the_answer_fails(client, alice, stub_llm):
    stub_llm.raise_error = LLMTimeout("timeout")
    response = ask(client, alice, query="A question that will fail")
    assert response.status_code == 503

    conversations = client.get(
        "/api/v1/chat/conversations", headers=alice.headers()
    ).json()["data"]["items"]
    assert len(conversations) == 1

    detail = client.get(
        f"/api/v1/chat/conversations/{conversations[0]['id']}", headers=alice.headers()
    ).json()["data"]
    assert detail["messages"][0]["content"] == "A question that will fail"


def test_mode_changes_the_system_prompt(client, alice, stub_llm):
    ask(client, alice, mode="compliance")
    compliance_system = stub_llm.systems[-1]

    ask(client, alice, mode="maintenance")
    maintenance_system = stub_llm.systems[-1]

    assert compliance_system != maintenance_system
    assert "compliance" in compliance_system.lower()
    assert "reliability" in maintenance_system.lower()


def test_confidence_is_capped_by_available_evidence(client, alice, stub_llm):
    """A model claiming 0.99 with no retrieved evidence must be discounted."""
    stub_llm.structured_response = {
        "executive_summary": "Confident about nothing.",
        "root_cause": "Unknown.",
        "supporting_evidence": [],
        "recommended_action": "None.",
        "business_impact": "None.",
        "risk_level": "Low",
        "confidence": 0.99,
    }
    decision = ask(client, alice).json()["data"]["decision"]
    assert decision["confidence"] is None
    assert decision["grounded"] is False


def test_invalid_risk_level_is_normalised():
    from app.schemas.agents import DecisionResponse
    decision = DecisionResponse(executive_summary="Summary", root_cause="", recommended_action="",
        business_impact="", risk_level="EXTREMELY SEVERE")
    assert decision.risk_level == "Medium"


def test_empty_query_is_rejected(client, alice, stub_llm):
    response = client.post(
        "/api/v1/chat/ask", json={"query": "   "}, headers=alice.headers()
    )
    assert response.status_code == 422
    assert stub_llm.call_count == 0


def test_oversized_query_is_rejected(client, alice, stub_llm):
    response = client.post(
        "/api/v1/chat/ask", json={"query": "x" * 5000}, headers=alice.headers()
    )
    assert response.status_code == 422
    assert stub_llm.call_count == 0


def test_reasoning_timeline_reports_each_agent(client, alice, stub_llm):
    timeline = ask(client, alice).json()["data"]["reasoning_timeline"]
    agents = {event["agent_name"] for event in timeline}
    assert "Coordinator" in agents
    assert len(timeline) >= 2
    assert all("duration_ms" in event for event in timeline)


def test_conversation_cannot_be_read_by_another_user(client, alice, bob, stub_llm):
    conversation_id = ask(client, alice).json()["data"]["conversation_id"]
    response = client.get(
        f"/api/v1/chat/conversations/{conversation_id}", headers=bob.headers()
    )
    assert response.status_code == 404


def test_conversation_can_be_renamed_and_deleted(client, alice, stub_llm):
    conversation_id = ask(client, alice).json()["data"]["conversation_id"]

    renamed = client.patch(
        f"/api/v1/chat/conversations/{conversation_id}",
        json={"title": "Pump investigation"},
        headers=alice.headers(),
    )
    assert renamed.json()["data"]["title"] == "Pump investigation"

    assert (
        client.delete(
            f"/api/v1/chat/conversations/{conversation_id}", headers=alice.headers()
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/chat/conversations/{conversation_id}", headers=alice.headers()
        ).status_code
        == 404
    )


def test_stream_emits_sse_events(client, alice, stub_llm):
    response = client.post(
        "/api/v1/chat/stream", json={"query": "Why is P-101 hot?"}, headers=alice.headers()
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    assert "event: conversation" in body
    assert "event: timeline" in body
    assert "event: decision" in body
    assert body.rstrip().endswith("data: {}")  # the terminal `done` event

    decision_line = next(
        line for line in body.splitlines()
        if line.startswith("data:") and "executive_summary" in line
    )
    assert json.loads(decision_line[len("data:"):])["decision"]["executive_summary"]


def test_stream_reports_failures_as_an_error_event(client, alice, stub_llm):
    stub_llm.raise_error = LLMTimeout("timeout")
    response = client.post(
        "/api/v1/chat/stream", json={"query": "Why is P-101 hot?"}, headers=alice.headers()
    )
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "event: done" in response.text


def test_specification_answer_can_omit_irrelevant_sections(stub_llm):
    from app.schemas.agents import AgentState, LLMDecision
    from app.services.agents.coordinator import coordinator_synthesis
    from app.services.agents.prompts import system_prompt
    claim = 'The rated operating pressure of Pump NF-731 is 6.4 bar.'
    payload = {'executive_summary': claim, 'supporting_evidence': [],
        'risk_level': None, 'confidence': 1.0,
        'references': [{'claim': claim, 'source_id': 'C1', 'quote': claim}]}
    raw = LLMDecision.model_validate(payload)
    assert raw.root_cause == raw.recommended_action == raw.business_impact == ''
    stub_llm.structured_response = payload
    state = AgentState(query='What is the rated pressure?', workspace_id='ws',
        semantic_chunks=[{'text': claim, 'document_id': 'doc'}])
    decision = coordinator_synthesis(state).final_decision
    assert decision.executive_summary == claim
    assert decision.evidence_status == 'references_checked'
    assert decision.root_cause == decision.recommended_action == decision.business_impact == ''
    assert 'specification lookup' in system_prompt('general')
    # Real-provider regression: uncited filler must still be rejected.
    payload['business_impact'] = 'None identified from the evidence.'
    assert coordinator_synthesis(state).final_decision.evidence_status == 'insufficient'


def test_risk_rating_requires_an_explicit_source_classification(stub_llm):
    from app.schemas.agents import AgentState
    from app.services.agents.coordinator import coordinator_synthesis
    quote = 'The inspection explicitly classifies the risk as High for this fault.'
    stub_llm.structured_response = {'executive_summary': quote, 'risk_level': 'High',
        'confidence': .9, 'references': [{'claim': quote, 'source_id': 'C1', 'quote': quote}]}
    state = AgentState(query='What is the risk?', workspace_id='ws',
        semantic_chunks=[{'text': quote, 'document_id': 'doc'}])
    assert coordinator_synthesis(state).final_decision.evidence_status == 'insufficient'
    stub_llm.structured_response['references'].append({'claim': 'High', 'source_id': 'C1', 'quote': quote})
    decision = coordinator_synthesis(state).final_decision
    assert decision.evidence_status == 'references_checked'
    assert decision.risk_level == 'High'
