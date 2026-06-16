import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from tools import AGENT_TYPES, CATEGORIES, PRIORITIES, SENTIMENTS, format_kb_context


load_dotenv()

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")

AGENT_SYSTEM_PROMPTS = {
    "IT": (
        "You are an expert IT support agent for a corporate helpdesk. Help with "
        "password resets, VPN issues, software installs, accounts, devices, and "
        "email tools. Be concise, practical, and empathetic."
    ),
    "HR": (
        "You are a helpful HR support agent. Help with leave, policy, onboarding, "
        "benefits, and employee process questions. Maintain confidentiality."
    ),
    "Security": (
        "You are a cybersecurity support agent. Help with phishing, access, data "
        "security, and incidents. Escalate active incidents immediately."
    ),
    "Finance": (
        "You are a finance and payroll support agent. Help with payroll, expenses, "
        "tax documents, reimbursements, and deductions. Ask for identity "
        "verification before sensitive advice."
    ),
    "General": (
        "You are a corporate helpdesk support agent. Route the employee to the "
        "right team and provide clear next steps."
    ),
}


def get_llm(temperature: float = 0.1, num_predict: int = 700) -> ChatOllama:
    options: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "temperature": temperature,
        "num_ctx": 4096,
        "num_predict": num_predict,
    }
    if OLLAMA_BASE_URL:
        options["base_url"] = OLLAMA_BASE_URL
    return ChatOllama(**options)


def extract_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model response")
    return json.loads(match.group(0))


def normalized_choice(value: str | None, choices: list[str], default: str) -> str:
    if not value:
        return default
    for choice in choices:
        if value.lower() == choice.lower():
            return choice
    return default


def fallback_classification(message: str) -> dict[str, Any]:
    text = message.lower()
    category = "General"
    agent_type = "General"
    sub_category = "general_inquiry"
    priority = "medium"
    sentiment = "neutral"
    actions = ["Acknowledge the employee", "Collect missing details", "Create a ticket if unresolved"]

    if any(word in text for word in ["password", "vpn", "wifi", "laptop", "software", "account", "login"]):
        category = "IT"
        agent_type = "IT"
        sub_category = "it_support"
        actions = ["Verify employee identity", "Collect error messages", "Try basic troubleshooting"]
    elif any(word in text for word in ["leave", "policy", "benefit", "onboarding", "hr"]):
        category = "HR"
        agent_type = "HR"
        sub_category = "hr_request"
    elif any(word in text for word in ["salary", "payroll", "reimbursement", "expense", "tax"]):
        category = "Payroll"
        agent_type = "Finance"
        sub_category = "payroll_query"
    elif any(word in text for word in ["phishing", "breach", "malware", "hacked", "security"]):
        category = "Security"
        agent_type = "Security"
        sub_category = "security_incident"
        priority = "high"
        actions = ["Do not click suspicious links", "Preserve evidence", "Escalate to Security"]

    if any(word in text for word in ["urgent", "critical", "cannot work", "blocked", "down"]):
        priority = "high"
    if any(word in text for word in ["breach", "hacked", "data leak"]):
        priority = "critical"
    if any(word in text for word in ["angry", "frustrated", "terrible", "useless", "never works", "awful"]):
        sentiment = "frustrated"
        priority = "high" if priority != "critical" else "critical"
    elif any(word in text for word in ["bad", "issue", "problem", "broken", "not working"]):
        sentiment = "negative"

    return {
        "category": category,
        "subCategory": sub_category,
        "priority": priority,
        "sentiment": sentiment,
        "agentType": agent_type,
        "confidence": 0.62,
        "suggestedActions": actions,
        "source": "fallback_rules",
    }


def classify_ticket(message: str) -> dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You classify employee helpdesk messages.

Return ONLY valid JSON with this exact shape:
{
  "category": "IT | HR | Payroll | Security | General",
  "subCategory": "short_snake_case_label",
  "priority": "low | medium | high | critical",
  "sentiment": "positive | neutral | negative | frustrated",
  "agentType": "IT | HR | Security | Finance | General",
  "confidence": 0.0,
  "suggestedActions": ["action 1", "action 2"]
}

Use Security for phishing, breach, malware, suspicious access, and data-loss issues.
Use Payroll for salary, tax, reimbursement, and paycheck issues.""",
            ),
            ("human", "{message}"),
        ]
    )

    try:
        result = (prompt | get_llm(num_predict=450) | StrOutputParser()).invoke({"message": message})
        data = extract_json(result)
    except Exception as exc:
        data = fallback_classification(message)
        data["modelWarning"] = str(exc)
        return data

    data["category"] = normalized_choice(data.get("category"), CATEGORIES, "General")
    data["priority"] = normalized_choice(data.get("priority"), PRIORITIES, "medium")
    data["sentiment"] = normalized_choice(data.get("sentiment"), SENTIMENTS, "neutral")
    data["agentType"] = normalized_choice(data.get("agentType"), AGENT_TYPES, "General")
    data["subCategory"] = str(data.get("subCategory") or "general_inquiry")

    try:
        data["confidence"] = max(0.0, min(float(data.get("confidence", 0.7)), 1.0))
    except (TypeError, ValueError):
        data["confidence"] = 0.7

    if not isinstance(data.get("suggestedActions"), list):
        data["suggestedActions"] = []
    data["source"] = "ollama"
    return data


def make_ticket_title(message: str) -> str:
    compact = " ".join(message.split())
    if not compact:
        return "Support request"
    sentence = re.split(r"[.!?]", compact)[0]
    return sentence[:80] or "Support request"


def format_history(history: list[dict[str, Any]], max_messages: int = 8) -> str:
    recent = history[-max_messages:]
    return "\n".join(f"{item['role']}: {item['content']}" for item in recent)


def answer_support_message(
    agent_type: str,
    message: str,
    history: list[dict[str, Any]],
    kb_documents: list[dict[str, Any]],
) -> str:
    agent_type = normalized_choice(agent_type, AGENT_TYPES, "General")
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", AGENT_SYSTEM_PROMPTS[agent_type]),
            (
                "human",
                """Conversation history:
{history}

Relevant knowledge base:
{kb_context}

Employee message:
{message}

Reply with:
1. A short acknowledgement.
2. Clear numbered troubleshooting or process steps.
3. What information you need from the employee.
4. Whether this should become a ticket or be escalated.

Keep the answer helpful and concise.""",
            ),
        ]
    )

    try:
        return (prompt | get_llm(temperature=0.2, num_predict=900) | StrOutputParser()).invoke(
            {
                "history": format_history(history),
                "kb_context": format_kb_context(kb_documents),
                "message": message,
            }
        )
    except Exception as exc:
        return (
            "I could not reach Ollama for the AI response. Based on the local "
            "helpdesk rules, please collect the employee name, exact error, "
            "affected system, urgency, and create a ticket if the issue is not "
            f"resolved. Technical detail: {exc}"
        )


def suggest_ticket_actions(ticket: dict[str, Any], kb_documents: list[dict[str, Any]]) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpdesk lead. Create a concise action plan for a support ticket.",
            ),
            (
                "human",
                """Ticket:
Title: {title}
Description: {description}
Category: {category}
Priority: {priority}
Sentiment: {sentiment}

Relevant knowledge base:
{kb_context}

Return a short plan with owner, next action, escalation need, and response draft.""",
            ),
        ]
    )

    try:
        return (prompt | get_llm(temperature=0.2, num_predict=650) | StrOutputParser()).invoke(
            {
                "title": ticket.get("title"),
                "description": ticket.get("description"),
                "category": ticket.get("category"),
                "priority": ticket.get("priority"),
                "sentiment": ticket.get("sentiment"),
                "kb_context": format_kb_context(kb_documents),
            }
        )
    except Exception as exc:
        return f"Ollama action-plan generation failed: {exc}"
