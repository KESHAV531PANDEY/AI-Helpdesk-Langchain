import html
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Streamlit keeps imported modules alive between reruns, so reload local app modules.
for module_name in ("tools", "pipeline", "agents"):
    sys.modules.pop(module_name, None)

from pipeline import (
    bootstrap,
    create_ticket_from_message,
    get_dashboard,
    start_conversation,
    submit_support_message,
    ticket_action_plan,
)
from tools import (
    AGENT_TYPES,
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    authenticate_user,
    create_kb_document,
    create_ticket,
    create_user,
    delete_kb_document,
    get_messages,
    list_kb_documents,
    list_tickets,
    search_knowledge_base,
    update_ticket_status,
)


st.set_page_config(
    page_title="AI Automator Helpdesk",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=JetBrains+Mono:wght@400;600;700&family=Roboto+Mono:wght@400;700&display=swap');

:root {
    --primary: #00d9ff;
    --primary-dark: #0097cc;
    --secondary: #ff006e;
    --accent: #ffbe0b;
    --accent-dark: #fb5607;
    --success: #06ffa5;
    --warning: #ff9f1c;
    --danger: #ff006e;
    --bg-dark: #0a0e27;
    --bg-darker: #050812;
    --surface: #1a1f3a;
    --surface-light: #252d48;
    --text-primary: #ffffff;
    --text-secondary: #b0b8d4;
    --border-glow: rgba(0, 217, 255, 0.3);
    --shadow-glow: 0 0 30px rgba(0, 217, 255, 0.15);
    --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.5);
}

* {
    font-family: 'JetBrains Mono', 'Space Mono', monospace;
}

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, var(--bg-darker) 0%, var(--bg-dark) 100%);
    color: var(--text-primary);
}

[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1f3a 0%, #0f1429 100%);
    border-right: 2px solid rgba(0, 217, 255, 0.2);
}

[data-testid="stSidebar"] * {
    color: var(--text-primary);
    font-family: 'JetBrains Mono', monospace;
}

.block-container {
    max-width: 1400px;
    padding: 2rem 2rem 3rem;
}

#MainMenu, footer {
    display: none;
}

h1, h2, h3, p {
    letter-spacing: 0.05em;
    font-family: 'Space Mono', monospace;
}

.brand-lockup {
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.1) 0%, rgba(255, 0, 110, 0.1) 100%);
    border: 2px solid rgba(0, 217, 255, 0.3);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1.5rem;
    box-shadow: var(--shadow-glow);
}

.brand-title {
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.2;
    background: linear-gradient(90deg, var(--primary) 0%, var(--secondary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.brand-subtitle {
    color: var(--text-secondary);
    font-size: 0.8rem;
    margin-top: 0.4rem;
    letter-spacing: 0.08em;
}

.sidebar-note {
    color: var(--text-secondary);
    font-size: 0.75rem;
    line-height: 1.6;
    border-top: 1px solid rgba(0, 217, 255, 0.2);
    padding-top: 1rem;
    margin-top: 1.2rem;
    background: rgba(0, 217, 255, 0.05);
    padding: 1rem;
    border-radius: 8px;
}

.page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1.5rem;
    margin-bottom: 2rem;
    padding: 1.5rem;
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.08) 0%, rgba(255, 0, 110, 0.08) 100%);
    border-left: 4px solid var(--primary);
    border-radius: 12px;
}

.eyebrow {
    color: var(--primary);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}

.page-title {
    font-size: 2.2rem;
    font-weight: 700;
    line-height: 1.1;
    background: linear-gradient(90deg, var(--primary) 0%, var(--accent) 50%, var(--secondary) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
}

.page-subtitle {
    max-width: 760px;
    color: var(--text-secondary);
    font-size: 0.95rem;
    line-height: 1.6;
    margin-top: 0.5rem;
}

.model-badge {
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.15) 0%, rgba(255, 190, 11, 0.15) 100%);
    border: 2px solid var(--primary);
    border-radius: 12px;
    padding: 1rem;
    min-width: 220px;
    box-shadow: var(--shadow-glow);
}

.badge-label {
    color: var(--text-secondary);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.badge-value {
    color: var(--primary);
    font-size: 1rem;
    font-weight: 700;
    margin-top: 0.3rem;
    letter-spacing: 0.05em;
}

.status-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1.2rem;
    margin-bottom: 2rem;
}

.metric-card {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: var(--shadow-lg);
    position: relative;
    overflow: hidden;
}

.metric-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
}

.metric-card:nth-child(2)::before {
    background: linear-gradient(90deg, var(--accent), var(--accent-dark));
}

.metric-card:nth-child(3)::before {
    background: linear-gradient(90deg, var(--danger), var(--secondary));
}

.metric-card:nth-child(4)::before {
    background: linear-gradient(90deg, var(--success), var(--primary));
}

.metric-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.75rem;
}

.metric-label {
    color: var(--text-secondary);
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.metric-value {
    color: var(--primary);
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1;
    margin-top: 0.8rem;
}

.metric-caption {
    color: var(--text-secondary);
    font-size: 0.8rem;
    margin-top: 0.5rem;
    letter-spacing: 0.03em;
}

.dot {
    width: 12px;
    height: 12px;
    border-radius: 999px;
    display: inline-block;
    background: var(--primary);
    box-shadow: 0 0 12px var(--primary);
}

.dot.blue { 
    background: #00d9ff;
    box-shadow: 0 0 12px rgba(0, 217, 255, 0.6);
}

.dot.amber { 
    background: var(--accent);
    box-shadow: 0 0 12px rgba(255, 190, 11, 0.6);
}

.dot.red { 
    background: var(--danger);
    box-shadow: 0 0 12px rgba(255, 0, 110, 0.6);
}

.dot.green { 
    background: var(--success);
    box-shadow: 0 0 12px rgba(6, 255, 165, 0.6);
}

.panel {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: var(--shadow-lg);
    margin-bottom: 1.5rem;
}

.panel-title {
    color: var(--primary);
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
    letter-spacing: 0.05em;
}

.panel-subtitle {
    color: var(--text-secondary);
    font-size: 0.85rem;
    margin-bottom: 1rem;
    letter-spacing: 0.03em;
}

.quick-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.quick-card {
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.1) 0%, rgba(255, 190, 11, 0.1) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    padding: 1rem;
    min-height: 100px;
    box-shadow: var(--shadow-glow);
}

.quick-title {
    color: var(--primary);
    font-weight: 700;
    font-size: 1rem;
}

.quick-copy {
    color: var(--text-secondary);
    font-size: 0.75rem;
    margin-top: 0.4rem;
    letter-spacing: 0.03em;
}

.chat-row {
    display: flex;
    margin: 1rem 0;
}

.chat-row.user {
    justify-content: flex-end;
}

.chat-bubble {
    max-width: 78%;
    border-radius: 12px;
    padding: 1rem;
    border: 2px solid rgba(0, 217, 255, 0.2);
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    color: var(--text-primary);
    line-height: 1.6;
    box-shadow: var(--shadow-lg);
}

.chat-row.user .chat-bubble {
    background: linear-gradient(135deg, var(--primary) 0%, #00a8cc 100%);
    color: var(--bg-dark);
    border-color: var(--primary);
}

.chat-role {
    color: var(--text-secondary);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
    letter-spacing: 0.1em;
}

.chat-row.user .chat-role {
    color: rgba(10, 14, 39, 0.7);
}

.pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    border-radius: 999px;
    padding: 0.4rem 0.8rem;
    font-size: 0.75rem;
    font-weight: 700;
    border: 1px solid rgba(0, 217, 255, 0.4);
    color: var(--text-primary);
    background: rgba(0, 217, 255, 0.15);
    margin: 0.2rem 0.2rem 0.2rem 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.pill.it, .pill.low, .pill.open, .pill.neutral {
    background: rgba(0, 217, 255, 0.2);
    color: var(--primary);
    border-color: var(--primary);
}

.pill.hr, .pill.medium, .pill.in_progress, .pill.positive {
    background: rgba(6, 255, 165, 0.2);
    color: var(--success);
    border-color: var(--success);
}

.pill.payroll, .pill.high, .pill.negative {
    background: rgba(255, 190, 11, 0.2);
    color: var(--accent);
    border-color: var(--accent);
}

.pill.security, .pill.critical, .pill.frustrated {
    background: rgba(255, 0, 110, 0.2);
    color: var(--danger);
    border-color: var(--danger);
}

.pill.resolved, .pill.closed {
    background: rgba(6, 255, 165, 0.2);
    color: var(--success);
    border-color: var(--success);
}

.ticket-card {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-left: 5px solid var(--primary);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-lg);
}

.ticket-card.critical {
    border-left-color: var(--danger);
}

.ticket-card.high {
    border-left-color: var(--accent);
}

.ticket-head {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
}

.ticket-title {
    color: var(--primary);
    font-size: 1.05rem;
    font-weight: 700;
}

.ticket-meta {
    color: var(--text-secondary);
    font-size: 0.8rem;
    margin-top: 0.3rem;
    letter-spacing: 0.03em;
}

.ticket-desc {
    color: var(--text-secondary);
    font-size: 0.9rem;
    line-height: 1.6;
    margin-top: 0.8rem;
}

.article-card {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    padding: 1.2rem;
    min-height: 220px;
    box-shadow: var(--shadow-lg);
}

.article-title {
    color: var(--primary);
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0.5rem 0;
}

.article-copy {
    color: var(--text-secondary);
    font-size: 0.85rem;
    line-height: 1.6;
}

.empty-state {
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.1) 0%, rgba(255, 0, 110, 0.1) 100%);
    border: 2px dashed rgba(0, 217, 255, 0.3);
    border-radius: 12px;
    padding: 2rem;
    color: var(--text-secondary);
    text-align: center;
}

div.stButton > button {
    border-radius: 8px;
    border: 2px solid rgba(0, 217, 255, 0.4);
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.2) 0%, rgba(255, 190, 11, 0.1) 100%);
    color: var(--primary);
    font-weight: 700;
    min-height: 2.6rem;
    letter-spacing: 0.05em;
    transition: all 0.3s ease;
}

div.stButton > button:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: linear-gradient(135deg, rgba(0, 217, 255, 0.3) 0%, rgba(255, 190, 11, 0.15) 100%);
    box-shadow: var(--shadow-glow);
}

div[data-testid="stForm"] {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    padding: 1.5rem;
    box-shadow: var(--shadow-lg);
}

div[data-testid="stExpander"] {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    box-shadow: var(--shadow-lg);
}

[data-testid="stDataFrame"] {
    border: 2px solid rgba(0, 217, 255, 0.2);
    border-radius: 12px;
    overflow: hidden;
}

.stDataFrame {
    background: linear-gradient(135deg, var(--surface) 0%, var(--surface-light) 100%);
}

@media (max-width: 900px) {
    .page-header {
        flex-direction: column;
    }
    .status-grid, .quick-row {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .chat-bubble {
        max-width: 92%;
    }
}

@media (max-width: 640px) {
    .status-grid, .quick-row {
        grid-template-columns: 1fr;
    }
    .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
    }
}
</style>
""",
    unsafe_allow_html=True,
)


def set_authenticated_user(user: dict) -> None:
    st.session_state.helpdesk_authenticated = True
    st.session_state.helpdesk_user_id = user.get("id")
    st.session_state.helpdesk_username = user.get("username")
    st.session_state.helpdesk_display_name = user.get("display_name") or user.get("username")
    st.session_state.helpdesk_role = user.get("role", "agent")


def require_login() -> None:
    if st.session_state.get("helpdesk_authenticated"):
        return

    st.markdown(
        """
<div class="page-header">
    <div>
        <div class="eyebrow">AI Automator Helpdesk</div>
        <h1 class="page-title">Sign In</h1>
        <div class="page-subtitle">Use your saved helpdesk account or create a new local account.</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    sign_in_tab, register_tab = st.tabs(["Sign In", "Create Account"])

    with sign_in_tab:
        with st.form("helpdesk_login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Start Project", use_container_width=True)

        if submitted:
            user = authenticate_user(username, password)
            if user:
                set_authenticated_user(user)
                st.rerun()
            else:
                st.error("Username or password is incorrect.")

    with register_tab:
        with st.form("helpdesk_register_form"):
            new_username = st.text_input("New username")
            display_name = st.text_input("Display name")
            new_password = st.text_input("New password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            register_submitted = st.form_submit_button("Create Account", use_container_width=True)

        if register_submitted:
            if new_password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    user = create_user(
                        username=new_username,
                        password=new_password,
                        display_name=display_name,
                    )
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    set_authenticated_user(user)
                    st.rerun()

    st.stop()


bootstrap()
require_login()


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def labelize(value: object) -> str:
    return esc(str(value or "").replace("_", " ").title())


def tone_class(value: object) -> str:
    return esc(str(value or "").lower().replace(" ", "_"))


def pill(value: object) -> str:
    return f'<span class="pill {tone_class(value)}">{labelize(value)}</span>'


def render_page_header(title: str, subtitle: str, agent_type: str | None = None) -> None:
    model_name = os.getenv("OLLAMA_MODEL", "llama3.2")
    agent = agent_type or "Local"
    st.markdown(
        f"""
<div class="page-header">
    <div>
        <div class="eyebrow">🤖 AI Automator Helpdesk</div>
        <h1 class="page-title">{esc(title)}</h1>
        <div class="page-subtitle">{esc(subtitle)}</div>
    </div>
    <div class="model-badge">
        <div class="badge-label">⚡ Local Runtime</div>
        <div class="badge-value">{esc(model_name)} / {esc(agent)}</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_metric(label: str, value: object, caption: str, tone: str = "blue") -> str:
    return f"""
<div class="metric-card">
    <div class="metric-top">
        <div class="metric-label">{esc(label)}</div>
        <span class="dot {esc(tone)}"></span>
    </div>
    <div class="metric-value">{esc(value)}</div>
    <div class="metric-caption">{esc(caption)}</div>
</div>
"""


def render_status_grid(stats: dict) -> None:
    st.markdown(
        f"""
<div class="status-grid">
    {render_metric("Total Tickets", stats["totalTickets"], "All support requests", "blue")}
    {render_metric("Open Queue", stats["openTickets"], "Open or in progress", "amber")}
    {render_metric("Critical", stats["criticalTickets"], "Needs immediate attention", "red")}
    {render_metric("Resolved", stats["resolvedTickets"], "Resolved or closed", "green")}
</div>
""",
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.markdown(f'<div class="empty-state">📭 {esc(message)}</div>', unsafe_allow_html=True)


def dataframe_or_empty(rows: list[dict], message: str) -> None:
    if not rows:
        empty_state(message)
        return
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def ensure_session_conversation(agent_type: str) -> int:
    if (
        "conversation_id" not in st.session_state
        or st.session_state.get("conversation_agent") != agent_type
    ):
        conversation = start_conversation(agent_type)
        st.session_state.conversation_id = conversation["id"]
        st.session_state.conversation_agent = agent_type
        st.session_state.last_classification = None
        st.session_state.last_user_message = None
    return int(st.session_state.conversation_id)


def render_chat_message(role: str, content: str) -> None:
    safe_content = esc(content).replace("\n", "<br>")
    role_label = "🤖 Agent" if role == "assistant" else "👤 Employee"
    role_class = "user" if role == "user" else "assistant"
    st.markdown(
        f"""
<div class="chat-row {role_class}">
    <div class="chat-bubble">
        <div class="chat-role">{role_label}</div>
        <div>{safe_content}</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_quick_actions() -> None:
    cards = [
        ("🔐 Password Reset", "Identity check, reset link, recovery steps"),
        ("🌐 VPN Not Working", "Network, MFA, profile, error code triage"),
        ("📊 Leave Balance", "Route to HR policy and approval guidance"),
        ("⚠️ Phishing Email", "Security escalation and evidence capture"),
    ]
    st.markdown(
        '<div class="quick-row">'
        + "".join(
            f"""
<div class="quick-card">
    <div class="quick-title">{esc(title)}</div>
    <div class="quick-copy">{esc(copy)}</div>
</div>
"""
            for title, copy in cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    quick_prompts = [
        "Reset my password",
        "VPN not working",
        "Check leave balance",
        "Report a phishing email",
    ]
    for index, action in enumerate(quick_prompts):
        if cols[index].button(action, use_container_width=True):
            st.session_state.pending_prompt = action


def render_agent_command(agent_type: str) -> None:
    stats = get_dashboard()
    render_page_header(
        "Agent Command Center",
        "Chat with a local Ollama support agent, classify the issue, and turn the conversation into a ticket.",
        agent_type,
    )
    render_status_grid(stats)
    render_quick_actions()

    conversation_id = ensure_session_conversation(agent_type)

    messages = get_messages(conversation_id)
    if messages:
        st.markdown(
            '<div class="panel"><div class="panel-title">💬 Live Support Chat</div>'
            '<div class="panel-subtitle">Conversation history for this active session.</div>',
            unsafe_allow_html=True,
        )
        for message in messages:
            render_chat_message(message["role"], message["content"])
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        empty_state("Start with a quick action or describe an employee issue in the chat box.")

    prompt = st.chat_input(f"💬 Ask {agent_type} support...")
    if st.session_state.get("pending_prompt"):
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        with st.spinner("🔄 Ollama is preparing the support response..."):
            result = submit_support_message(conversation_id, prompt, agent_type)
        st.session_state.last_classification = result["classification"]
        st.session_state.last_user_message = prompt
        st.rerun()

    classification = st.session_state.get("last_classification")
    last_message = st.session_state.get("last_user_message")
    if classification and last_message:
        st.markdown(
            '<div class="panel"><div class="panel-title">🎯 Latest AI Triage</div>'
            '<div class="panel-subtitle">Classification from the most recent employee message.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
{pill(classification.get("category", "General"))}
{pill(classification.get("priority", "medium"))}
{pill(classification.get("sentiment", "neutral"))}
<span class="pill">✓ Confidence {float(classification.get("confidence", 0)):.0%}</span>
""",
            unsafe_allow_html=True,
        )

        actions = classification.get("suggestedActions") or []
        if actions:
            st.write("💡 Suggested Actions")
            for action in actions:
                st.markdown(f"- {action}")
        st.markdown("</div>", unsafe_allow_html=True)

        with st.form("create_ticket_from_chat"):
            st.markdown("**🎫 Create Ticket From Latest Message**")
            employee_name = st.text_input("Employee Name", placeholder="Optional")
            employee_id = st.text_input("Employee ID", placeholder="Optional")
            submitted = st.form_submit_button("✨ Create Ticket")
            if submitted:
                ticket = create_ticket_from_message(
                    message=last_message,
                    classification=classification,
                    employee_name=employee_name or None,
                    employee_id=employee_id or None,
                    conversation_id=conversation_id,
                )
                st.success(f"✅ Ticket #{ticket['id']} created.")


def render_ticket_card(ticket: dict) -> None:
    priority = tone_class(ticket.get("priority"))
    description = esc(ticket.get("description", ""))[:260]
    st.markdown(
        f"""
<div class="ticket-card {priority}">
    <div class="ticket-head">
        <div>
            <div class="ticket-title">#{ticket["id"]} - {esc(ticket["title"])}</div>
            <div class="ticket-meta">
                👤 {esc(ticket.get("employee_name") or "Unknown")} | 📅 {esc(ticket.get("created_at"))}
            </div>
        </div>
        <div>{pill(ticket.get("status"))} {pill(ticket.get("priority"))}</div>
    </div>
    <div style="margin-top:0.6rem;">
        {pill(ticket.get("category"))} {pill(ticket.get("sentiment"))}
    </div>
    <div class="ticket-desc">{description}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_tickets() -> None:
    render_page_header(
        "Ticket Management",
        "Create, filter, update, and generate action plans for employee support requests.",
    )

    with st.expander("🎫 Create a New Ticket", expanded=False):
        with st.form("manual_ticket_form"):
            title = st.text_input("Title")
            description = st.text_area("Description", height=120)
            col1, col2, col3 = st.columns(3)
            category = col1.selectbox("Category", CATEGORIES)
            priority = col2.selectbox("Priority", PRIORITIES, index=1)
            employee_name = col3.text_input("Employee Name")
            submitted = st.form_submit_button("✨ Create Ticket")
            if submitted:
                if not title or not description:
                    st.warning("⚠️ Title and description are required.")
                else:
                    ticket = create_ticket(
                        title=title,
                        description=description,
                        category=category,
                        priority=priority,
                        employee_name=employee_name or None,
                    )
                    st.success(f"✅ Ticket #{ticket['id']} created.")

    st.markdown(
        '<div class="panel"><div class="panel-title">🔍 Queue Filters</div>'
        '<div class="panel-subtitle">Narrow the support queue by status, priority, category, or search text.</div>',
        unsafe_allow_html=True,
    )
    f1, f2, f3, f4 = st.columns([1, 1, 1, 2])
    status_filter = f1.selectbox("Status", ["all"] + STATUSES)
    priority_filter = f2.selectbox("Priority", ["all"] + PRIORITIES)
    category_filter = f3.selectbox("Category", ["all"] + CATEGORIES)
    search = f4.text_input("🔎 Search Tickets")
    st.markdown("</div>", unsafe_allow_html=True)

    tickets = list_tickets(
        status=status_filter,
        priority=priority_filter,
        category=category_filter,
        search=search,
    )

    if not tickets:
        empty_state("No tickets match the current filters.")
        return

    table_rows = [
        {
            "id": ticket["id"],
            "title": ticket["title"],
            "requester": ticket.get("employee_name") or "Unknown",
            "category": ticket["category"],
            "priority": ticket["priority"],
            "status": ticket["status"],
            "sentiment": ticket["sentiment"],
            "created_at": ticket["created_at"],
        }
        for ticket in tickets
    ]

    st.markdown("#### 📋 Queue Snapshot")
    dataframe_or_empty(table_rows, "No tickets match the current filters.")

    st.markdown("#### 🎫 Ticket Cards")
    for ticket in tickets[:12]:
        render_ticket_card(ticket)

    st.markdown(
        '<div class="panel"><div class="panel-title">⚙️ Ticket Operations</div>'
        '<div class="panel-subtitle">Update status or ask Ollama for an action plan.</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1, 2])
    ticket_ids = [ticket["id"] for ticket in tickets]
    selected_id = c1.selectbox("Ticket ID", ticket_ids)
    new_status = c2.selectbox("New Status", STATUSES)
    if c3.button("🔄 Update Status", use_container_width=True):
        update_ticket_status(int(selected_id), new_status)
        st.success(f"✅ Ticket #{selected_id} updated.")
        st.rerun()

    if st.button("🚀 Generate Action Plan For Selected Ticket", use_container_width=True):
        with st.spinner("🤖 Ollama is writing the action plan..."):
            st.session_state.ticket_plan = ticket_action_plan(int(selected_id))

    if st.session_state.get("ticket_plan"):
        st.markdown(st.session_state.ticket_plan)
    st.markdown("</div>", unsafe_allow_html=True)


def render_article_card(doc: dict) -> str:
    tags = "".join(pill(tag) for tag in doc.get("tags", [])[:4])
    content = esc(doc.get("content", ""))[:210]
    return f"""
<div class="article-card">
    {pill(doc.get("category"))}
    <div class="article-title">📄 {esc(doc.get("title"))}</div>
    <div class="article-copy">{content}</div>
    <div style="margin-top:0.75rem;">{tags}</div>
</div>
"""


def render_knowledge_base() -> None:
    render_page_header(
        "Knowledge Base",
        "Manage local articles that the Ollama agent uses for better answers.",
    )

    with st.expander("📝 Publish a New Article", expanded=False):
        with st.form("kb_form"):
            title = st.text_input("Article Title")
            category = st.selectbox("Article Category", CATEGORIES)
            tags_raw = st.text_input("Tags", placeholder="comma separated")
            content = st.text_area("Article Content", height=180)
            submitted = st.form_submit_button("✨ Publish Article")
            if submitted:
                if not title or not content:
                    st.warning("⚠️ Title and content are required.")
                else:
                    tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
                    create_kb_document(title=title, content=content, category=category, tags=tags)
                    st.success("✅ Article created.")
                    st.rerun()

    search = st.text_input("🔎 Search Articles", placeholder="vpn, password, payroll, phishing")
    docs = search_knowledge_base(search) if search else list_kb_documents()

    if not docs:
        empty_state("No knowledge base articles found.")
        return

    st.markdown(
        '<div class="panel"><div class="panel-title">📚 Article Library</div>'
        '<div class="panel-subtitle">Quick scan view for local support knowledge.</div></div>',
        unsafe_allow_html=True,
    )

    rows = [docs[index : index + 3] for index in range(0, len(docs), 3)]
    for row in rows:
        columns = st.columns(3)
        for column, doc in zip(columns, row):
            column.markdown(render_article_card(doc), unsafe_allow_html=True)

    delete_options = {f"#{doc['id']} - {doc['title']}": doc["id"] for doc in docs}
    d1, d2 = st.columns([3, 1])
    selected = d1.selectbox("Delete Article", list(delete_options.keys()))
    if d2.button("🗑️ Delete", use_container_width=True):
        delete_kb_document(delete_options[selected])
        st.success("✅ Article deleted.")
        st.rerun()

    st.markdown("#### 📖 Full Article Preview")
    for doc in docs:
        with st.expander(f"{doc['title']} ({doc['category']})"):
            st.write(doc["content"])
            if doc.get("tags"):
                st.caption("Tags: " + ", ".join(doc["tags"]))


def create_colorful_chart(data: dict, title: str, color_scheme: list) -> go.Figure:
    """Create a beautiful, colorful Plotly chart"""
    fig = go.Figure(data=[
        go.Bar(
            x=list(data.keys()),
            y=list(data.values()),
            marker=dict(
                color=list(data.values()),
                colorscale=color_scheme,
                showscale=False,
                line=dict(color='rgba(0, 217, 255, 0.5)', width=2)
            ),
            text=list(data.values()),
            textposition='auto',
            textfont=dict(color='white', size=12, family='JetBrains Mono'),
        )
    ])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, color='#00d9ff', family='Space Mono')),
        xaxis=dict(
            tickfont=dict(color='#b0b8d4', size=11),
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 217, 255, 0.1)',
        ),
        yaxis=dict(
            tickfont=dict(color='#b0b8d4', size=11),
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 217, 255, 0.1)',
        ),
        plot_bgcolor='rgba(10, 14, 39, 0.3)',
        paper_bgcolor='rgba(10, 14, 39, 0)',
        margin=dict(l=40, r=40, t=60, b=40),
        hovermode='x unified',
        font=dict(family='JetBrains Mono'),
    )
    
    return fig


def create_sentiment_pie_chart(data: dict) -> go.Figure:
    """Create a vibrant pie/donut chart for sentiment"""
    colors = ['#06ffa5', '#00d9ff', '#ffbe0b', '#ff006e']
    
    fig = go.Figure(data=[go.Pie(
        labels=list(data.keys()),
        values=list(data.values()),
        hole=0.4,
        marker=dict(
            colors=colors,
            line=dict(color='#0a0e27', width=3)
        ),
        textfont=dict(color='white', size=12, family='JetBrains Mono'),
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
    )])
    
    fig.update_layout(
        title=dict(text='🎭 Sentiment Breakdown', font=dict(size=18, color='#00d9ff', family='Space Mono')),
        paper_bgcolor='rgba(10, 14, 39, 0)',
        font=dict(family='JetBrains Mono', color='#b0b8d4'),
        margin=dict(l=20, r=20, t=60, b=20),
    )
    
    return fig


def render_dashboard() -> None:
    stats = get_dashboard()
    render_page_header(
        "Dashboard",
        "Live support metrics from the local SQLite database with real-time AI insights.",
    )
    render_status_grid(stats)

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(
            '<div class="panel"><div class="panel-title">📊 Tickets by Category</div>'
            '<div class="panel-subtitle">Where the support load is coming from.</div>',
            unsafe_allow_html=True,
        )
        if stats["ticketsByCategory"]:
            fig = create_colorful_chart(
                stats["ticketsByCategory"], 
                "Category Distribution",
                ['#00d9ff', '#ffbe0b', '#ff006e', '#06ffa5']
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("No category data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown(
            '<div class="panel"><div class="panel-title">⚡ Priority Distribution</div>'
            '<div class="panel-subtitle">How urgent the current queue is.</div>',
            unsafe_allow_html=True,
        )
        if stats["ticketsByPriority"]:
            fig = create_colorful_chart(
                stats["ticketsByPriority"], 
                "Priority Levels",
                ['#ff006e', '#ffbe0b', '#00d9ff', '#06ffa5']
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            empty_state("No priority data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="panel"><div class="panel-title">🎭 Sentiment Analysis</div>'
        '<div class="panel-subtitle">AI-detected employee tone across all tickets (Beautiful Visualization).</div>',
        unsafe_allow_html=True,
    )
    if stats["sentimentBreakdown"]:
        fig = create_sentiment_pie_chart(stats["sentimentBreakdown"])
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state("No sentiment data yet.")
    st.markdown("</div>", unsafe_allow_html=True)


st.sidebar.markdown(
    """
<div class="brand-lockup">
    <div class="brand-title">🚀 AI AUTOMATOR</div>
    <div class="brand-subtitle">Local Ollama Helpdesk Operations</div>
</div>
""",
    unsafe_allow_html=True,
)

signed_in_name = st.session_state.get("helpdesk_display_name") or st.session_state.get(
    "helpdesk_username",
    "User",
)
st.sidebar.caption(f"Signed in as {signed_in_name}")
if st.sidebar.button("Sign out", use_container_width=True):
    st.session_state.helpdesk_authenticated = False
    st.session_state.pop("helpdesk_user_id", None)
    st.session_state.pop("helpdesk_username", None)
    st.session_state.pop("helpdesk_display_name", None)
    st.session_state.pop("helpdesk_role", None)
    st.rerun()

agent_type = st.sidebar.selectbox("🤖 Active Agent", AGENT_TYPES)
page = st.sidebar.radio(
    "📍 Workspace",
    ["Agent Command", "Tickets", "Knowledge Base", "Dashboard"],
)

st.sidebar.markdown(
    """
<div class="sidebar-note">
✅ Run Ollama locally<br>
✅ Keep the knowledge base updated<br>
✅ Use tickets for tracking and escalation<br>
✅ Monitor metrics in real-time
</div>
""",
    unsafe_allow_html=True,
)

if page == "Agent Command":
    render_agent_command(agent_type)
elif page == "Tickets":
    render_tickets()
elif page == "Knowledge Base":
    render_knowledge_base()
else:
    render_dashboard()
