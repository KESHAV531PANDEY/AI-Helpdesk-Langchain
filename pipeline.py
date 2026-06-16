from typing import Any

from agents import answer_support_message, classify_ticket, make_ticket_title, suggest_ticket_actions
from tools import (
    create_conversation,
    create_ticket,
    dashboard_stats,
    ensure_ready,
    get_messages,
    get_ticket,
    list_tickets,
    save_message,
    search_knowledge_base,
)


def bootstrap() -> None:
    ensure_ready()


def start_conversation(agent_type: str = "IT") -> dict[str, Any]:
    bootstrap()
    return create_conversation(title="New Support Chat", agent_type=agent_type)


def submit_support_message(conversation_id: int, content: str, active_agent: str = "IT") -> dict[str, Any]:
    bootstrap()

    user_message = save_message(conversation_id, "user", content)
    classification = classify_ticket(content)
    agent_type = classification.get("agentType") or active_agent
    kb_documents = search_knowledge_base(content)
    history = get_messages(conversation_id, limit=8)
    assistant_reply = answer_support_message(agent_type, content, history, kb_documents)
    assistant_message = save_message(conversation_id, "assistant", assistant_reply)

    return {
        "conversationId": conversation_id,
        "userMessage": user_message,
        "assistantMessage": assistant_message,
        "reply": assistant_reply,
        "classification": classification,
        "knowledgeBase": kb_documents,
        "lowConfidence": float(classification.get("confidence", 0.0)) < 0.7,
    }


def create_ticket_from_message(
    message: str,
    classification: dict[str, Any],
    employee_name: str | None = None,
    employee_id: str | None = None,
    conversation_id: int | None = None,
) -> dict[str, Any]:
    return create_ticket(
        title=make_ticket_title(message),
        description=message,
        category=classification.get("category", "General"),
        priority=classification.get("priority", "medium"),
        sentiment=classification.get("sentiment", "neutral"),
        employee_name=employee_name,
        employee_id=employee_id,
        conversation_id=conversation_id,
        ai_confidence=classification.get("confidence"),
    )


def ticket_action_plan(ticket_id: int) -> str:
    ticket = get_ticket(ticket_id)
    if not ticket:
        return "Ticket not found."
    kb_documents = search_knowledge_base(f"{ticket['title']} {ticket['description']}")
    return suggest_ticket_actions(ticket, kb_documents)


def get_dashboard() -> dict[str, Any]:
    bootstrap()
    return dashboard_stats()


def get_recent_tickets(limit: int = 10) -> list[dict[str, Any]]:
    bootstrap()
    return list_tickets()[:limit]


def run_ticket_pipeline(message: str) -> dict[str, Any]:
    bootstrap()
    classification = classify_ticket(message)
    kb_documents = search_knowledge_base(message)
    return {
        "classification": classification,
        "knowledgeBase": kb_documents,
        "ticketTitle": make_ticket_title(message),
    }
