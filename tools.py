import json
import os
import hashlib
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
import secrets
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
configured_db_path = os.getenv("HELPDESK_DB_PATH", "helpdesk_automator.db")
DB_PATH = (
    configured_db_path
    if Path(configured_db_path).is_absolute()
    else str(PROJECT_DIR / configured_db_path)
)

CATEGORIES = ["IT", "HR", "Payroll", "Security", "General"]
PRIORITIES = ["low", "medium", "high", "critical"]
STATUSES = ["open", "in_progress", "resolved", "closed"]
SENTIMENTS = ["positive", "neutral", "negative", "frustrated"]
AGENT_TYPES = ["IT", "HR", "Security", "Finance", "General"]
PASSWORD_HASH_ITERATIONS = 240_000


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    data = dict(row)
    if "tags_json" in data:
        try:
            data["tags"] = json.loads(data.pop("tags_json") or "[]")
        except json.JSONDecodeError:
            data["tags"] = []
    return data


def normalize_username(username: str) -> str:
    return username.strip()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False

    try:
        algorithm, iterations, salt, expected_digest = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    try:
        iteration_count = int(iterations)
    except ValueError:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iteration_count,
    ).hex()
    return secrets.compare_digest(digest, expected_digest)


def init_database() -> None:
    with connect() as connection:
        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'agent',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique
            ON users(username COLLATE NOCASE)
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'IT',
                priority TEXT NOT NULL DEFAULT 'medium',
                status TEXT NOT NULL DEFAULT 'open',
                sentiment TEXT NOT NULL DEFAULT 'neutral',
                employee_id TEXT,
                employee_name TEXT,
                conversation_id INTEGER,
                ai_confidence REAL,
                resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS kb_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'IT',
                tags_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                agent_type TEXT NOT NULL DEFAULT 'IT',
                created_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES conversations(id)
            )
            """
        )

        connection.commit()


def create_user(
    username: str,
    password: str,
    display_name: str | None = None,
    role: str = "agent",
) -> dict[str, Any]:
    username = normalize_username(username)
    display_name = (display_name or username).strip() or username
    role = role if role in {"admin", "agent"} else "agent"

    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")

    timestamp = now_iso()

    with connect() as connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (
                    username, password_hash, display_name, role,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    username,
                    hash_password(password),
                    display_name,
                    role,
                    timestamp,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("That username is already registered.") from exc

        connection.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,))
        return row_to_dict(cursor.fetchone()) or {}


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    username = normalize_username(username)
    if not username or not password:
        return None

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        )
        user = row_to_dict(cursor.fetchone())
        if not user or not verify_password(password, user.get("password_hash")):
            return None

        cursor.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now_iso(), user["id"]),
        )
        connection.commit()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user["id"],))
        return row_to_dict(cursor.fetchone())


def seed_default_user() -> None:
    username = normalize_username(os.getenv("HELPDESK_LOGIN_USERNAME", "admin"))
    password = os.getenv("HELPDESK_LOGIN_PASSWORD", "admin123")
    if not username or not password:
        return

    with connect() as connection:
        existing = connection.execute(
            "SELECT id FROM users WHERE username = ? COLLATE NOCASE",
            (username,),
        ).fetchone()

    if existing:
        return

    create_user(username=username, password=password, display_name="Admin", role="admin")


def seed_knowledge_base() -> None:
    samples = [
        {
            "title": "VPN connection checklist",
            "category": "IT",
            "tags": ["vpn", "network", "remote"],
            "content": (
                "Confirm internet access, restart the VPN client, verify MFA, "
                "check whether the employee is using the latest VPN profile, "
                "then ask for the error code before escalating."
            ),
        },
        {
            "title": "Password reset process",
            "category": "IT",
            "tags": ["password", "account", "login"],
            "content": (
                "Verify the employee identity, confirm the username, send the "
                "approved reset link, and ask the employee to update recovery "
                "methods after login."
            ),
        },
        {
            "title": "Phishing report procedure",
            "category": "Security",
            "tags": ["phishing", "security", "email"],
            "content": (
                "Ask the employee not to click links, forward the email headers "
                "to security, isolate the device if attachments were opened, "
                "and create a high priority security ticket."
            ),
        },
        {
            "title": "Leave balance and approval",
            "category": "HR",
            "tags": ["leave", "hr", "policy"],
            "content": (
                "Employees can check balances in the HR portal. Approval depends "
                "on manager confirmation and policy rules for the leave type."
            ),
        },
        {
            "title": "Payroll discrepancy triage",
            "category": "Payroll",
            "tags": ["payroll", "salary", "finance"],
            "content": (
                "Verify employee identity, collect pay period details, compare "
                "expected and received amounts, and route sensitive cases to "
                "Finance or Payroll."
            ),
        },
    ]

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM kb_documents")
        if cursor.fetchone()["count"] > 0:
            return

        for sample in samples:
            create_kb_document(
                title=sample["title"],
                content=sample["content"],
                category=sample["category"],
                tags=sample["tags"],
                connection=connection,
            )

        connection.commit()


def ensure_ready() -> None:
    init_database()
    seed_default_user()
    seed_knowledge_base()


def create_conversation(title: str, agent_type: str = "IT") -> dict[str, Any]:
    agent_type = agent_type if agent_type in AGENT_TYPES else "General"
    created_at = now_iso()

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO conversations (title, agent_type, created_at)
            VALUES (?, ?, ?)
            """,
            (title, agent_type, created_at),
        )
        connection.commit()
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,))
        return row_to_dict(cursor.fetchone()) or {}


def get_messages(conversation_id: int, limit: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC"
    params: list[Any] = [conversation_id]

    if limit:
        query = (
            "SELECT * FROM ("
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?"
            ") ORDER BY id ASC"
        )
        params.append(limit)

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) or {} for row in rows]


def save_message(conversation_id: int, role: str, content: str) -> dict[str, Any]:
    created_at = now_iso()
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO messages (conversation_id, role, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, role, content, created_at),
        )
        connection.commit()
        cursor.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,))
        return row_to_dict(cursor.fetchone()) or {}


def create_ticket(
    title: str,
    description: str,
    category: str = "General",
    priority: str = "medium",
    status: str = "open",
    sentiment: str = "neutral",
    employee_id: str | None = None,
    employee_name: str | None = None,
    conversation_id: int | None = None,
    ai_confidence: float | None = None,
) -> dict[str, Any]:
    category = category if category in CATEGORIES else "General"
    priority = priority if priority in PRIORITIES else "medium"
    status = status if status in STATUSES else "open"
    sentiment = sentiment if sentiment in SENTIMENTS else "neutral"
    created_at = now_iso()

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO tickets (
                title, description, category, priority, status, sentiment,
                employee_id, employee_name, conversation_id, ai_confidence,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                description,
                category,
                priority,
                status,
                sentiment,
                employee_id,
                employee_name,
                conversation_id,
                ai_confidence,
                created_at,
                created_at,
            ),
        )
        connection.commit()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (cursor.lastrowid,))
        return row_to_dict(cursor.fetchone()) or {}


def list_tickets(
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []

    if status and status != "all":
        clauses.append("status = ?")
        params.append(status)
    if priority and priority != "all":
        clauses.append("priority = ?")
        params.append(priority)
    if category and category != "all":
        clauses.append("category = ?")
        params.append(category)
    if search:
        clauses.append("(title LIKE ? OR description LIKE ? OR employee_name LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term, term])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM tickets {where_sql} ORDER BY id DESC"

    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) or {} for row in rows]


def get_ticket(ticket_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return row_to_dict(row)


def update_ticket_status(ticket_id: int, status: str) -> dict[str, Any] | None:
    if status not in STATUSES:
        raise ValueError(f"Unknown status: {status}")

    resolved_at = now_iso() if status in {"resolved", "closed"} else None
    updated_at = now_iso()

    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE tickets
            SET status = ?, resolved_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, resolved_at, updated_at, ticket_id),
        )
        connection.commit()
        cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        return row_to_dict(cursor.fetchone())


def create_kb_document(
    title: str,
    content: str,
    category: str = "IT",
    tags: list[str] | None = None,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    category = category if category in CATEGORIES else "General"
    tags = tags or []
    timestamp = now_iso()

    owns_connection = connection is None
    connection = connection or connect()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO kb_documents (title, content, category, tags_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title, content, category, json.dumps(tags), timestamp, timestamp),
    )

    if owns_connection:
        connection.commit()

    cursor.execute("SELECT * FROM kb_documents WHERE id = ?", (cursor.lastrowid,))
    document = row_to_dict(cursor.fetchone()) or {}

    if owns_connection:
        connection.close()

    return document


def list_kb_documents() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute("SELECT * FROM kb_documents ORDER BY id DESC").fetchall()
        return [row_to_dict(row) or {} for row in rows]


def search_knowledge_base(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return list_kb_documents()[:limit]

    words = [word.strip().lower() for word in query.split() if len(word.strip()) > 2]
    docs = list_kb_documents()

    def score(doc: dict[str, Any]) -> int:
        haystack = " ".join(
            [
                doc.get("title", ""),
                doc.get("content", ""),
                doc.get("category", ""),
                " ".join(doc.get("tags", [])),
            ]
        ).lower()
        return sum(haystack.count(word) for word in words)

    ranked = sorted(docs, key=score, reverse=True)
    return [doc for doc in ranked if score(doc) > 0][:limit] or ranked[: min(limit, len(ranked))]


def delete_kb_document(document_id: int) -> None:
    with connect() as connection:
        connection.execute("DELETE FROM kb_documents WHERE id = ?", (document_id,))
        connection.commit()


def dashboard_stats() -> dict[str, Any]:
    tickets = list_tickets()
    total = len(tickets)
    open_count = sum(1 for ticket in tickets if ticket["status"] in {"open", "in_progress"})
    resolved_count = sum(1 for ticket in tickets if ticket["status"] in {"resolved", "closed"})
    critical_count = sum(1 for ticket in tickets if ticket["priority"] == "critical")
    frustrated_count = sum(1 for ticket in tickets if ticket["sentiment"] == "frustrated")

    resolution_hours = []
    for ticket in tickets:
        if not ticket.get("resolved_at"):
            continue
        try:
            created = datetime.fromisoformat(ticket["created_at"])
            resolved = datetime.fromisoformat(ticket["resolved_at"])
            resolution_hours.append((resolved - created).total_seconds() / 3600)
        except ValueError:
            continue

    return {
        "totalTickets": total,
        "openTickets": open_count,
        "resolvedTickets": resolved_count,
        "criticalTickets": critical_count,
        "frustratedEmployees": frustrated_count,
        "avgResolutionHours": round(sum(resolution_hours) / len(resolution_hours), 1)
        if resolution_hours
        else 0,
        "ticketsByCategory": dict(Counter(ticket["category"] for ticket in tickets)),
        "ticketsByPriority": dict(Counter(ticket["priority"] for ticket in tickets)),
        "sentimentBreakdown": dict(Counter(ticket["sentiment"] for ticket in tickets)),
    }


def format_kb_context(documents: list[dict[str, Any]], max_chars: int = 2400) -> str:
    blocks = []
    for document in documents:
        tags = ", ".join(document.get("tags", []))
        blocks.append(
            f"Title: {document.get('title')}\n"
            f"Category: {document.get('category')}\n"
            f"Tags: {tags}\n"
            f"Content: {document.get('content')}"
        )

    text = "\n\n---\n\n".join(blocks)
    return text[:max_chars]


@tool
def knowledge_base_search(query: str) -> str:
    """Search local helpdesk knowledge base articles."""
    return format_kb_context(search_knowledge_base(query))


@tool
def create_helpdesk_ticket(description: str) -> str:
    """Create a basic helpdesk ticket from a support issue description."""
    ticket = create_ticket(
        title=description[:80] or "Support request",
        description=description,
        category="General",
        priority="medium",
    )
    return f"Created ticket #{ticket['id']}: {ticket['title']}"
