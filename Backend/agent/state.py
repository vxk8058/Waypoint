"""Request-local graph state and latest-per-product result merging."""
from typing import Annotated, Any, Required, TypedDict

from ..auth.users import PublicUser
from .schemas import ProductResult, RouteDecision, VerifyDecision


def merge_results(current: list[ProductResult], updates: list[ProductResult]) -> list[ProductResult]:
    # A failed re-fetch must replace an earlier success, too, so stale facts cannot win.
    by_product = {result.product: result for result in current}
    by_product.update((result.product, result) for result in updates)
    return list(by_product.values())


class AgentState(TypedDict, total=False):
    query: Required[str]
    user_id: Required[str]
    profile_id: Required[str]
    route: RouteDecision
    results: Annotated[list[ProductResult], merge_results]
    verify: VerifyDecision
    iterations: int
    final_ui: dict[str, Any]


def initial_state(query: str, user: PublicUser) -> AgentState:
    """Call with the server-authenticated user, never user-supplied profile IDs."""
    query = query.strip()
    if not query:
        raise ValueError("A banking question is required")
    return {"query": query, "user_id": user.user_id, "profile_id": user.profile_id,
            "results": [], "iterations": 0}
