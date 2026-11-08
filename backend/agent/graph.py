"""Main agent graph and its parent/subgraph boundaries."""
import logging
from functools import partial

from langgraph.graph import END, START, StateGraph

from ..services.profile_service import ProfileService
from .nodes.eval_query import eval_query, route_to_products
from .nodes.gen_ui import gen_ui
from .nodes.verify import after_verify, verify
from .state import AgentState
from .subgraphs.checking import build_checking_graph
from .subgraphs.credit_card import build_credit_card_graph
from .subgraphs.loans import build_loans_graph
from .subgraphs.other_data import build_other_data_graph
from .subgraphs.savings import build_savings_graph

log = logging.getLogger("waypoint.agent")


def make_subgraph_node(subgraph):
    def node(state: AgentState):
        verification = state.get("verify")
        out = subgraph.invoke({
            "query": state["query"],
            "profile_id": state["profile_id"],
            "missing": verification.missing if verification else "",
            "refresh": bool(verification and not verification.done),
        })
        return {"results": [out["result"]]}
    return node


def build_subgraph_nodes(profiles: ProfileService, worker=None):
    """Use with fresh parent state from initial_state(query, authenticated_user)."""
    builders = {
        "checking": build_checking_graph,
        "savings": build_savings_graph,
        "credit_card": build_credit_card_graph,
        "loans": build_loans_graph,
        "other_data": build_other_data_graph,
    }
    return {product: make_subgraph_node(builder(profiles, worker)) for product, builder in builders.items()}


def build_agent_graph(profiles: ProfileService, planner=None, worker=None):
    """No checkpointer: invoke with fresh initial_state(query, authenticated_user) per request."""
    branches = build_subgraph_nodes(profiles, worker)
    graph = StateGraph(AgentState)
    graph.add_node("eval_query", partial(eval_query, planner=planner))
    for name, node in branches.items():
        graph.add_node(name, node)
        graph.add_edge(name, "verify")  # parallel branches finish in one superstep, so Verify runs once per round
    graph.add_node("verify", partial(verify, planner=planner))
    graph.add_node("gen_ui", partial(gen_ui, planner=planner))
    graph.add_edge(START, "eval_query")
    graph.add_conditional_edges("eval_query", route_to_products, [*branches, "gen_ui"])
    graph.add_conditional_edges("verify", after_verify, ["eval_query", "gen_ui"])
    graph.add_edge("gen_ui", END)
    return graph.compile()


def run_agent(graph, state: AgentState) -> AgentState:
    """Invoke and log the execution path only: no question text, identities, amounts, or summaries."""
    final = state
    for mode, chunk in graph.stream(state, stream_mode=["updates", "values"]):
        if mode == "values":
            final = chunk
            continue
        for node, update in chunk.items():
            update = update or {}
            if node == "eval_query":
                detail = f"products={update['route'].products}" if "route" in update else ""
            elif node == "verify":
                v = update["verify"]
                detail = (f"round={update['iterations']} done={v.done} need_products={v.need_products} "
                          f"need_other_data={v.need_other_data}")
            elif node == "gen_ui":
                detail = f"blocks={[b['type'] for b in update['final_ui']['blocks']]}"
            else:
                r = update["results"][0]
                detail = f"confidence={r.confidence} errors={len(r.errors)}"
            log.info("agent node=%s %s", node, detail)
    return final
