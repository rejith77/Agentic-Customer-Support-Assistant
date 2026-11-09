import re
from typing import Any, Literal, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.config import settings
from app.data_store import CustomerData
from app.policy_rag import PolicyRetriever


RouteName = Literal["excel", "rag", "both", "general"]


class Route(BaseModel):
    route: RouteName = Field(description="Choose Excel for workbook facts, RAG for policy, both for cross-source questions")


class AgentState(TypedDict, total=False):
    question: str
    route: RouteName
    facts: list[str]
    policy_evidence: list[str]
    draft: str
    answer: str


class SupportAgent:
    """A small LangGraph workflow: supervisor, retrieval, then response validation."""

    def __init__(self, data: CustomerData, policy: PolicyRetriever):
        self.data = data
        self.policy = policy
        self.llm = ChatOpenAI(model=settings.openai_model, temperature=0, api_key=settings.openai_api_key)
        self.router = self.llm.with_structured_output(Route)

        builder = StateGraph(AgentState)
        builder.add_node("supervisor", self.supervisor)
        builder.add_node("excel_agent", self.excel_agent)
        builder.add_node("rag_pipeline", self.rag_pipeline)
        builder.add_node("both_sources", self.both_sources)
        builder.add_node("validator", self.validator)
        builder.add_edge(START, "supervisor")
        builder.add_conditional_edges("supervisor", lambda state: state["route"], {
            "excel": "excel_agent", "rag": "rag_pipeline", "both": "both_sources", "general": "validator",
        })
        for node in ("excel_agent", "rag_pipeline", "both_sources"):
            builder.add_edge(node, "validator")
        builder.add_edge("validator", END)
        self.graph = builder.compile()

    def supervisor(self, state: AgentState) -> dict[str, Any]:
        question = state["question"]
        fallback = self._fallback_route(question)
        try:
            route = self.router.invoke(
                "Route this customer support question. Choose excel for customer, order, or product facts from "
                "the workbook; rag for refund/return policy questions; both when answering requires an order or "
                "product lookup plus policy; general for other questions.\nQuestion: " + question
            )
            selected = route.route
        except Exception:
            selected = fallback
        return {"route": selected, "facts": [], "policy_evidence": []}

    @staticmethod
    def _fallback_route(question: str) -> RouteName:
        q = question.lower()
        has_order = bool(re.search(r"\bO\d+\b", question, re.I))
        policy_words = ("refund", "return", "exchange", "policy", "shipping fee", "eligible", "qualify")
        data_words = ("customer", "email", "phone", "city", "profile", "order", "purchase", "product", "price", "category")
        wants_policy = any(word in q for word in policy_words)
        wants_data = has_order or any(word in q for word in data_words)
        if wants_policy and wants_data:
            return "both"
        if wants_policy:
            return "rag"
        if wants_data:
            return "excel"
        return "general"

    @staticmethod
    def _ids(question: str, prefix: str) -> list[str]:
        return list(dict.fromkeys(re.findall(rf"\b{prefix}\d+\b", question.upper())))

    def excel_agent(self, state: AgentState) -> dict[str, Any]:
        """Look up referenced IDs in the workbook and return source facts to the validator."""
        question = state["question"]
        customer_ids = self._ids(question, "C")
        order_ids = self._ids(question, "O")
        product_ids = self._ids(question, "P")
        facts: list[str] = []

        for customer_id in customer_ids:
            row = self.data.customer(customer_id)
            facts.append(f"Customer {customer_id}: {row if row else 'not found'}")
        for order_id in order_ids:
            row = self.data.order(order_id)
            if row:
                row = dict(row)
                row["Product"] = self.data.product(str(row.get("ProductID", "")))
                row["Customer"] = self.data.customer(str(row.get("CustomerID", "")))
            facts.append(f"Order {order_id}: {row if row else 'not found'}")
        for product_id in product_ids:
            row = self.data.product(product_id)
            facts.append(f"Product {product_id}: {row if row else 'not found'}")

        if not facts:
            if "order" in question.lower() or "purchase" in question.lower():
                facts.append("No order or customer ID was included. Ask for an order ID (O001) or customer ID (C001).")
            elif "product" in question.lower() or "price" in question.lower():
                facts.append("No product ID was included. Ask for a product ID (P001).")
            else:
                facts.append("No customer, order, or product ID was included. Ask the customer for the relevant ID.")
        return {"facts": facts}

    def rag_pipeline(self, state: AgentState) -> dict[str, Any]:
        excerpts = self.policy.search(state["question"])
        return {"policy_evidence": excerpts}

    def both_sources(self, state: AgentState) -> dict[str, Any]:
        excel_result = self.excel_agent(state)
        rag_result = self.rag_pipeline(state)
        return {**excel_result, **rag_result}

    def validator(self, state: AgentState) -> dict[str, Any]:
        facts = state.get("facts", [])
        excerpts = state.get("policy_evidence", [])
        prompt = (
            "You are the final response validator for a customer support assistant. Answer the user's question "
            "clearly and only use the supplied workbook facts and policy excerpts. If a lookup says not found, say so. "
            "If required information is missing, explain what is missing instead of guessing. In particular, the "
            "workbook OrderDate is not necessarily delivery date; refund eligibility requires policy conditions "
            "such as delivery date, item condition, packaging, invoice, and final-sale status. Keep the answer concise. "
            "For general questions with no retrieved facts, ask a short clarifying question and do not invent policy.\n\n"
            f"User question:\n{state['question']}\n\nWorkbook facts:\n{facts}\n\nPolicy excerpts:\n{excerpts}"
        )
        result = self.llm.invoke(prompt)
        return {"answer": result.content}

    def ask(self, question: str) -> dict[str, Any]:
        result = self.graph.invoke({"question": question})
        return {
            "answer": result["answer"],
            "route": result.get("route", "general"),
            "facts": result.get("facts", []),
            "evidence": result.get("policy_evidence", []),
        }
