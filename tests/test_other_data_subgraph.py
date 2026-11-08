import json
from threading import Barrier
from unittest.mock import Mock, patch

import pytest

from backend.agent.data import get_data
from backend.agent.subgraphs.other_data import SourceDecision, build_other_data_graph
from backend.services.profile_service import ProfileService


@pytest.fixture
def other(primary):
    profile = primary.unified.model_copy(deep=True)
    profile.data_mode = "nessie"
    profile.metadata = {"stale": False, "warnings": []}
    service = Mock(spec=ProfileService)
    service.get.return_value = profile
    worker = Mock()
    selection, evaluation = Mock(), Mock()
    selection.invoke.return_value = {"sources": ["transactions"]}
    evaluation.invoke.return_value = {"summary": "Extra records available.", "confidence": 0.9}
    worker.with_structured_output.side_effect = lambda schema: selection if schema is SourceDecision else evaluation
    graph = build_other_data_graph(service, worker)
    return profile, service, selection, evaluation, graph


def invoke(graph, profile):
    return graph.invoke({"query": "Why did my balance change?", "profile_id": profile.profile_id,
                         "missing": "Need transaction history"})["result"]


@pytest.mark.parametrize("source", ["transactions", "bio"])
def test_only_selected_source_is_fetched(other, source):
    profile, service, selection, evaluation, graph = other
    selection.invoke.return_value = {"sources": [source]}
    with patch("backend.agent.subgraphs.other_data.get_data", wraps=get_data) as fetch:
        result = invoke(graph, profile)
    fetch.assert_called_once_with(service, profile.profile_id, source, refresh=False)
    assert result.product == "other_data" and set(result.data) == {source}
    assert result.data[source] == get_data(service, profile.profile_id, source)
    assert result.errors == [] and result.confidence == 0.9
    evaluation.invoke.assert_called_once()
    assert "Need transaction history" in selection.invoke.call_args.args[0]


def test_parallel_fetches_join_before_one_evaluation(other):
    profile, _, selection, evaluation, graph = other
    selection.invoke.return_value = {"sources": ["transactions", "bio"]}
    barrier = Barrier(2, timeout=5)
    def fetch(*args, **kwargs):
        barrier.wait()
        return get_data(*args, **kwargs)
    with patch("backend.agent.subgraphs.other_data.get_data", side_effect=fetch):
        result = invoke(graph, profile)
    assert set(result.data) == {"transactions", "bio"} and result.errors == []
    evaluation.invoke.assert_called_once()
    prompt = evaluation.invoke.call_args.args[0]
    payload = json.loads(prompt.split("\n", 1)[1])
    assert payload["data"] == result.data


@pytest.mark.parametrize("sources", [[], ["other_api"]])
def test_empty_or_unconfigured_sources_do_not_fetch_or_evaluate(other, sources):
    profile, service, selection, evaluation, graph = other
    selection.invoke.return_value = {"sources": sources}
    result = invoke(graph, profile)
    assert result.data == {} and result.confidence == 0 and result.errors
    service.get.assert_not_called()
    evaluation.invoke.assert_not_called()


@pytest.mark.parametrize("sources", [["unknown"], ["bio", "bio"]])
def test_invalid_selection_is_bounded_and_cannot_fetch(other, sources):
    profile, service, selection, evaluation, graph = other
    selection.invoke.return_value = {"sources": sources}
    result = invoke(graph, profile)
    assert selection.invoke.call_count == 3
    assert result.errors == ["Other data selection failed (RuntimeError)"]
    assert result.data == {} and result.confidence == 0
    service.get.assert_not_called()
    evaluation.invoke.assert_not_called()


def test_partial_failure_keeps_successful_source(other):
    profile, service, selection, evaluation, graph = other
    selection.invoke.return_value = {"sources": ["transactions", "bio"]}
    def fetch(profiles, profile_id, source, **kwargs):
        if source == "bio":
            raise ConnectionError("private-token")
        return get_data(profiles, profile_id, source, **kwargs)
    with patch("backend.agent.subgraphs.other_data.get_data", side_effect=fetch):
        result = invoke(graph, profile)
    assert set(result.data) == {"transactions"} and result.confidence == 0
    assert result.errors == ["bio retrieval failed (ConnectionError)"]
    assert "private-token" not in result.model_dump_json()
    evaluation.invoke.assert_called_once()


def test_failed_evaluation_keeps_trusted_data_and_warnings(other):
    profile, _, _, evaluation, graph = other
    profile.data_mode = "pre_seed"
    profile.metadata = {"stale": True, "warnings": ["Source warning"]}
    evaluation.invoke.return_value = {"summary": "Invented", "confidence": 1, "data": {}}
    result = invoke(graph, profile)
    assert result.confidence == 0 and evaluation.invoke.call_count == 3
    assert result.data["transactions"]["metadata"] == profile.metadata
    assert result.errors == ["transactions: Source warning", "transactions: data is a stale snapshot",
                             "transactions: data is synthetic pre-seed data",
                             "Other data evaluation failed (RuntimeError)"]


def test_repeated_invocation_does_not_keep_old_sources(other):
    profile, _, selection, _, graph = other
    assert set(invoke(graph, profile).data) == {"transactions"}
    selection.invoke.return_value = {"sources": []}
    assert invoke(graph, profile).data == {}
