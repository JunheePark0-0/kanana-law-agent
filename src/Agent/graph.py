from langgraph.graph import StateGraph, END, START

from src.Agent.states import LegalAgentState
from src.Agent.functions import (
    route_by_input_type,
    route_after_document_parsing,
    route_by_enough_context,
    route_by_enough_answer,
    should_regenerate,
)
from src.Agent.nodes import (
    routing_node,
    query_rewriting_node,
    document_parsing_node,
    issue_extracting_node,
    rag_searching_node,
    context_evaluating_node,
    web_searching_node,
    context_reranking_node,
    context_filtering_node,
    answer_generating_node,
    answer_evaluating_node,
    answer_regenerating_node,
)


def legal_agent():
    """Legal Agent 그래프"""
    workflow = StateGraph(LegalAgentState)

    # 노드 추가
    workflow.add_node("input_router", routing_node)
    workflow.add_node("query_rewriter", query_rewriting_node)
    workflow.add_node("document_parser", document_parsing_node)
    workflow.add_node("issue_extractor", issue_extracting_node)
    workflow.add_node("rag_searcher", rag_searching_node)
    workflow.add_node("context_evaluator", context_evaluating_node)
    workflow.add_node("web_searcher", web_searching_node)
    workflow.add_node("context_reranker", context_reranking_node)
    workflow.add_node("context_filter", context_filtering_node)
    workflow.add_node("answer_generator", answer_generating_node)
    workflow.add_node("answer_evaluator", answer_evaluating_node)
    workflow.add_node("answer_regenerator", answer_regenerating_node)

    # 엣지 추가
    workflow.add_edge(START, "input_router")
    workflow.add_edge("input_router", "query_rewriter")
    workflow.add_conditional_edges(
        "query_rewriter",
        route_by_input_type,
        {"Query_Only": "rag_searcher", "Hybrid": "document_parser", "Error": END},
    )
    workflow.add_conditional_edges(
        "document_parser",
        route_after_document_parsing,
        {"Hybrid": "issue_extractor", "Query_Only": "rag_searcher", "Error": END},
    )
    workflow.add_edge("issue_extractor", "rag_searcher")
    workflow.add_edge("rag_searcher", "context_evaluator")
    workflow.add_conditional_edges(
        "context_evaluator",
        route_by_enough_context,
        {"ENOUGH": "answer_generator", "NOT_ENOUGH": "web_searcher"},
    )
    workflow.add_edge("web_searcher", "context_filter")
    workflow.add_edge("context_filter", "context_reranker")
    workflow.add_edge("context_reranker", "context_evaluator")
    workflow.add_edge("answer_generator", "answer_evaluator")
    workflow.add_conditional_edges(
        "answer_evaluator",
        route_by_enough_answer,
        {"ENOUGH": END, "NOT_ENOUGH": "answer_regenerator"},
    )
    workflow.add_conditional_edges(
        "answer_regenerator",
        should_regenerate,
        {"YES": "answer_evaluator", "NO": END},
    )

    return workflow.compile()
