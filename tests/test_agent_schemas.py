from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from backend.agent.llm import structured
from backend.agent.schemas import ProductEvaluation, ProductResult, RouteDecision, VerifyDecision


def test_worker_cannot_supply_trusted_fields():
    for field, value in {"product": "savings", "data": {"balance": 999}, "errors": []}.items():
        with pytest.raises(ValidationError):
            ProductEvaluation(summary="Balance available", confidence=0.8, **{field: value})
    evaluation = ProductEvaluation(summary="Balance available", confidence=0.8)
    result = ProductResult(product="checking", data={"balance": 2450},
                           errors=["stale snapshot"], **evaluation.model_dump())
    assert result.data == {"balance": 2450}
    assert result.errors == ["stale snapshot"]


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf"), True, "0.5"])
def test_invalid_confidence(confidence):
    with pytest.raises(ValidationError):
        ProductEvaluation(summary="Summary", confidence=confidence)


@pytest.mark.parametrize("product", ["checking", "savings", "credit_card", "loans", "other_data"])
def test_product_results(product):
    result = ProductResult(product=product, summary="No data available", confidence=0, data={})
    assert result.product == product
    assert result.errors == []


@pytest.mark.parametrize("payload", [
    {"products": ["investments"], "reasoning": "Unknown"},
    {"products": ["other_data"], "reasoning": "Not a product route"},
    {"products": ["checking", "checking"], "reasoning": "Duplicate"},
    {"products": [], "reasoning": "  "},
    {"products": ["checking"], "reasoning": "Balance", "user_id": "someone-else"},
])
def test_invalid_routes(payload):
    with pytest.raises(ValidationError):
        RouteDecision.model_validate(payload)


def test_multi_product_and_no_match_routes():
    assert RouteDecision(products=["savings", "loans"], reasoning="Compare").products == ["savings", "loans"]
    assert RouteDecision(products=[], reasoning="Please specify a banking question").products == []


@pytest.mark.parametrize("payload", [
    {"done": True, "need_products": ["checking"]},
    {"done": True, "need_other_data": True},
    {"done": True, "missing": "Transactions"},
    {"done": False},
    {"done": False, "missing": "  "},
    {"done": False, "missing": "Balance", "need_products": ["checking", "checking"]},
    {"done": False, "missing": "Balance", "need_products": ["unknown"]},
    {"done": "false", "missing": "Balance"},
])
def test_invalid_verification(payload):
    with pytest.raises(ValidationError):
        VerifyDecision.model_validate(payload)


def test_complete_retry_and_clarification_decisions():
    assert VerifyDecision(done=True).missing == ""
    retry = VerifyDecision(done=False, missing="Need balance and transactions",
                           need_products=["checking"], need_other_data=True)
    assert retry.need_products == ["checking"] and retry.need_other_data
    clarify = VerifyDecision(done=False, missing="Which account do you mean?")
    assert not clarify.need_products and not clarify.need_other_data


def test_structured_helper_retries_contradictory_decision():
    model = Mock()
    model.with_structured_output.return_value.invoke.side_effect = [
        {"done": True, "need_other_data": True}, {"done": True},
    ]
    assert structured(model, VerifyDecision, "Verify").done
    assert model.with_structured_output.return_value.invoke.call_count == 2


def test_unknown_result_product_is_rejected():
    with pytest.raises(ValidationError):
        ProductResult(product="unknown", summary="Summary", confidence=1, data={})
