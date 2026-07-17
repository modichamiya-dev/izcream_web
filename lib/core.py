from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests


DISCORD_API = "https://discord.com/api/v10"
COMPONENTS_V2 = 1 << 15
PRIVATE_THREAD = 12
TEXT_CHANNELS = {0, 5}
FORUM_CHANNELS = {15, 16}


def env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip().strip("'\"")
        if value:
            return value
    return ""


BOT_TOKEN = env("DISCORD_BOT_TOKEN", "DISCORD_TOKEN", "BOT_TOKEN")
SUPPORT_CHANNEL = env("DISCORD_CHANNEL_ID", "SUPPORT_CHANNEL_ID", "CHANNEL_ID")
LOG_CHANNEL = env("DISCORD_LOG_CHANNEL", "DISCORD_LOG_CHANNEL_ID", "LOG_CHANNEL_ID")
STAFF_ROLE = env("DISCORD_STAFF_ROLE_ID", "STAFF_ROLE_ID")
WEBHOOK_URL = env("DISCORD_WEBHOOK_URL", "DISCORD_WEBHOOK", "WEBHOOK_URL")
IZCREAM_LOGO_URL = env("IZCREAM_LOGO_URL") or "https://izcream.gg/storage/site/logos/images/68daaaad297d7.webp"
EXPLICIT_SESSION_SECRET = env("SESSION_SECRET")
SESSION_SECRET = EXPLICIT_SESSION_SECRET or (
    hashlib.sha256(f"izcream-vercel-session:{BOT_TOKEN}".encode()).hexdigest()
    if BOT_TOKEN else ""
)
SETUP_SECRET = env("SETUP_SECRET")
CRON_SECRET = env("CRON_SECRET")


def now_ms() -> int:
    return int(time.time() * 1000)


def clean(value: Any, limit: int = 1500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def markdown(value: Any, limit: int = 1500) -> str:
    return clean(value, limit).replace("`", "'").replace("@", "@\u200b")


def slug(value: Any, limit: int = 70) -> str:
    text = re.sub(r"[^\w .-]", "", clean(value, 80))
    text = re.sub(r"\s+", "-", text)
    return (re.sub(r"-+", "-", text).strip("-") or "visitor")[:limit]


def b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def sign_session(data: dict[str, Any]) -> str:
    if not SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET is not configured")
    payload = b64encode(json.dumps(data, separators=(",", ":")).encode())
    signature = b64encode(hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"v1.{payload}.{signature}"


def read_session(token: Any) -> dict[str, Any] | None:
    parts = str(token or "").split(".")
    if len(parts) != 3 or parts[0] != "v1" or not SESSION_SECRET:
        return None
    expected = b64encode(hmac.new(SESSION_SECRET.encode(), parts[1].encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, parts[2]):
        return None
    try:
        data = json.loads(b64decode(parts[1]))
        return data if isinstance(data, dict) else None
    except (ValueError, json.JSONDecodeError):
        return None


def discord(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    if not BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not configured")
    response = requests.request(
        method,
        f"{DISCORD_API}{path}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": "IZCREAM-Vercel/1.0"},
        json=payload,
        timeout=12,
    )
    if not response.ok:
        raise RuntimeError(f"Discord API {path} failed with {response.status_code}: {response.text[:180]}")
    return response.json() if response.content else None


def event_components(title: str, detail: str, color: int) -> dict[str, Any]:
    return {
        "flags": COMPONENTS_V2,
        "allowed_mentions": {"parse": []},
        "components": [{
            "type": 17,
            "accent_color": color,
            "components": [
                {"type": 10, "content": f"## {markdown(title, 120)}"},
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 10, "content": markdown(detail, 1400)},
            ],
        }],
    }


def intro_components(ticket: dict[str, Any], first_message: str) -> dict[str, Any]:
    return {
        "flags": COMPONENTS_V2,
        "allowed_mentions": {"parse": []},
        "components": [{
            "type": 17,
            "accent_color": 0xE93BF8,
            "components": [
                {"type": 10, "content": (
                    "# New IZCREAM Support Chat\n"
                    f"**Rainbet:** `{markdown(ticket['username'], 80)}`\n"
                    f"**Category:** {markdown(ticket['category'], 100)}\n"
                    f"**Session:** `{ticket['id']}`\n"
                    f"**Created:** <t:{int(ticket['createdAt'] / 1000)}:F>"
                )},
                {"type": 14, "divider": True, "spacing": 1},
                {"type": 10, "content": f"**First message**\n{markdown(first_message, 900)}"},
                {"type": 10, "content": "Reply normally to answer the visitor. Use `/close` or the button below when complete."},
                {"type": 1, "components": [{
                    "type": 2,
                    "style": 4,
                    "label": "Close thread",
                    "custom_id": f"izcream_close:{ticket['id']}",
                }]},
            ],
        }],
    }


def add_staff(thread_id: str, guild_id: str) -> None:
    if not STAFF_ROLE:
        return
    after = "0"
    while True:
        members = discord("GET", f"/guilds/{quote(guild_id)}/members?limit=1000&after={quote(after)}")
        for member in members or []:
            user = member.get("user") or {}
            if STAFF_ROLE in map(str, member.get("roles", [])) and user.get("id") and not user.get("bot"):
                discord("PUT", f"/channels/{thread_id}/thread-members/{user['id']}")
        if not isinstance(members, list) or len(members) < 1000:
            return
        after = str((members[-1].get("user") or {}).get("id") or "")
        if not after:
            return


def create_thread(ticket: dict[str, Any], first_message: str) -> str:
    if not SUPPORT_CHANNEL:
        raise RuntimeError("DISCORD_CHANNEL_ID is not configured")
    parent = discord("GET", f"/channels/{SUPPORT_CHANNEL}")
    channel_type = int(parent.get("type", -1))
    name = f"support-{slug(ticket['username'])}-{ticket['id'][-6:]}"[:100]
    if channel_type in FORUM_CHANNELS:
        payload = {"name": name, "auto_archive_duration": 1440, "message": intro_components(ticket, first_message)}
    elif channel_type in TEXT_CHANNELS:
        payload = {"name": name, "type": PRIVATE_THREAD, "invitable": False, "auto_archive_duration": 1440}
    else:
        raise RuntimeError(f"Unsupported support channel type {channel_type}")
    thread = discord("POST", f"/channels/{SUPPORT_CHANNEL}/threads", payload)
    thread_id = str(thread["id"])
    try:
        add_staff(thread_id, str(parent.get("guild_id") or ""))
    except RuntimeError:
        pass
    if channel_type not in FORUM_CHANNELS:
        discord("POST", f"/channels/{thread_id}/messages", intro_components(ticket, first_message))
    return thread_id


def send_visitor(thread_id: str, username: str, message: str) -> None:
    if WEBHOOK_URL:
        separator = "&" if "?" in WEBHOOK_URL else "?"
        response = requests.post(
            f"{WEBHOOK_URL}{separator}wait=true&thread_id={quote(thread_id)}",
            json={
                "username": clean(username, 80),
                "avatar_url": IZCREAM_LOGO_URL,
                "content": markdown(message, 1800),
                "allowed_mentions": {"parse": []},
            },
            timeout=12,
        )
        if response.ok:
            return
    discord("POST", f"/channels/{thread_id}/messages", {
        "content": f"**{markdown(username, 80)}:** {markdown(message, 1700)}",
        "allowed_mentions": {"parse": []},
    })


def open_or_read_ticket(body: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    existing = read_session(body.get("sessionId"))
    if existing and existing.get("threadId"):
        try:
            state = ticket_thread_state(existing)
            if not state["closed"]:
                if state["archived"]:
                    discord("PATCH", f"/channels/{existing['threadId']}", {"archived": False})
                return existing, False
        except RuntimeError as error:
            if "failed with 404" not in str(error):
                raise
    username = clean(body.get("rainbetUsername") or body.get("name"), 32)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        raise ValueError("Invalid Rainbet username")
    ticket = {
        "id": f"web_{now_ms():x}_{hashlib.sha256(os.urandom(16)).hexdigest()[:8]}",
        "username": username,
        "category": clean(body.get("category"), 100) or "Something else",
        "createdAt": now_ms(),
    }
    ticket["threadId"] = create_thread(ticket, clean(body.get("message"), 1200))
    return ticket, True


def parse_discord_time(value: Any) -> int:
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return now_ms()


def staff_replies(ticket: dict[str, Any], after: int) -> list[dict[str, Any]]:
    messages = discord("GET", f"/channels/{ticket['threadId']}/messages?limit=100") or []
    replies = []
    for message in reversed(messages):
        author = message.get("author") or {}
        created = parse_discord_time(message.get("timestamp"))
        if created <= after or message.get("webhook_id") or author.get("bot"):
            continue
        attachments = message.get("attachments") or []
        text = str(message.get("content") or "").strip()
        if attachments:
            text += ("\n" if text else "") + "\n".join(str(item.get("url") or "") for item in attachments)
        replies.append({
            "id": str(message.get("id")), "role": "staff", "text": text or "[Attachment]",
            "name": clean(author.get("global_name") or author.get("username") or "Staff", 60),
            "createdAt": created,
        })
    return replies


def ticket_thread_state(ticket: dict[str, Any]) -> dict[str, bool]:
    channel = discord("GET", f"/channels/{ticket['threadId']}")
    metadata = channel.get("thread_metadata") or {}
    return {
        "closed": bool(metadata.get("locked")),
        "archived": bool(metadata.get("archived")),
    }


def chat_history(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    username = clean(ticket.get("username"), 80)
    visitor_prefix = f"**{username}:**"
    for message in thread_messages(str(ticket["threadId"])):
        author = message.get("author") or {}
        content = str(message.get("content") or "").strip()
        attachments = message.get("attachments") or []
        if attachments:
            content += ("\n" if content else "") + "\n".join(str(item.get("url") or "") for item in attachments)

        if message.get("webhook_id"):
            role = "user"
            name = username
        elif author.get("bot") and content.startswith(visitor_prefix):
            role = "user"
            name = username
            content = content[len(visitor_prefix):].strip()
        elif not author.get("bot"):
            role = "staff"
            name = clean(author.get("global_name") or author.get("username") or "Staff", 60)
        else:
            continue

        if content:
            history.append({
                "id": str(message.get("id")),
                "role": role,
                "text": content,
                "name": name,
                "createdAt": parse_discord_time(message.get("timestamp")),
            })
    return history


def process_text_close_command(ticket: dict[str, Any]) -> str | None:
    messages = discord("GET", f"/channels/{ticket['threadId']}/messages?limit=25") or []
    for message in messages:
        author = message.get("author") or {}
        if author.get("bot") or message.get("webhook_id"):
            continue
        if clean(message.get("content"), 40).lower() != "!close":
            continue
        closed_by = clean(author.get("global_name") or author.get("username") or "IZCREAM Staff", 80)
        close_ticket(str(ticket["threadId"]), closed_by)
        return closed_by
    return None


def scan_active_threads_for_close() -> dict[str, Any]:
    parent = discord("GET", f"/channels/{SUPPORT_CHANNEL}")
    guild_id = str(parent.get("guild_id") or "")
    active = discord("GET", f"/guilds/{guild_id}/threads/active") or {}
    checked = 0
    closed: list[str] = []
    errors: list[str] = []
    for thread in active.get("threads", []):
        thread_id = str(thread.get("id") or "")
        if not thread_id or str(thread.get("parent_id") or "") != SUPPORT_CHANNEL:
            continue
        checked += 1
        try:
            ticket = metadata_from_thread(thread_id)
            if process_text_close_command(ticket):
                closed.append(thread_id)
        except Exception as error:
            errors.append(f"{thread_id}: {str(error)[:120]}")
    return {"checked": checked, "closed": closed, "errors": errors}


def thread_messages(thread_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    before = ""
    while len(result) < 1000:
        suffix = f"?limit=100&before={before}" if before else "?limit=100"
        page = discord("GET", f"/channels/{thread_id}/messages{suffix}") or []
        result.extend(page)
        if len(page) < 100:
            break
        before = str(page[-1].get("id") or "")
        if not before:
            break
    return list(reversed(result))


def transcript(thread_id: str, ticket: dict[str, Any], closed_by: str) -> tuple[str, bytes]:
    filename = f"ticket-{slug(ticket.get('username'))}-{slug(ticket.get('id'))[-16:]}.txt"
    lines = [
        "IZCREAM SUPPORT TICKET TRANSCRIPT", "=" * 34,
        f"Session: {ticket.get('id', 'Unknown')}", f"Discord thread: {thread_id}",
        f"Rainbet username: {ticket.get('username', 'Unknown')}",
        f"Category: {ticket.get('category', 'Unknown')}", f"Closed by: {closed_by}",
        f"Closed at: {datetime.utcnow().isoformat()}Z", "", "MESSAGES", "=" * 34,
    ]
    for message in thread_messages(thread_id):
        author = message.get("author") or {}
        content = str(message.get("content") or "").strip()
        attachments = [f"Attachment: {a.get('filename', 'file')} - {a.get('url', '')}" for a in message.get("attachments", [])]
        if content or attachments:
            lines.extend([
                f"[{message.get('timestamp', 'Unknown time')}] {clean(author.get('global_name') or author.get('username') or 'Unknown', 80)}:",
                content, *attachments, "",
            ])
    return filename, ("\n".join(lines).rstrip() + "\n").encode("utf-8")


def metadata_from_thread(thread_id: str) -> dict[str, Any]:
    ticket = {"id": "Unknown", "username": "Unknown", "category": "Unknown", "threadId": thread_id}
    for message in thread_messages(thread_id):
        stack = list(message.get("components") or [])
        while stack:
            component = stack.pop()
            stack.extend(component.get("components") or [])
            content = str(component.get("content") or "")
            for key, pattern in {
                "username": r"\*\*Rainbet:\*\*\s*`([^`]+)`",
                "category": r"\*\*Category:\*\*\s*([^\n]+)",
                "id": r"\*\*Session:\*\*\s*`([^`]+)`",
            }.items():
                match = re.search(pattern, content)
                if match:
                    ticket[key] = clean(match.group(1), 100)
    return ticket


def close_ticket(thread_id: str, closed_by: str) -> None:
    channel = discord("GET", f"/channels/{thread_id}")
    if str(channel.get("parent_id") or "") != SUPPORT_CHANNEL:
        raise RuntimeError("This command can only close IZCREAM support threads")
    if not LOG_CHANNEL:
        raise RuntimeError("DISCORD_LOG_CHANNEL is not configured; the thread was not deleted")
    ticket = metadata_from_thread(thread_id)
    filename, raw = transcript(thread_id, ticket, clean(closed_by, 80) or "IZCREAM Staff")
    payload = event_components(
        "Ticket closed and logged",
        (
            f"**Rainbet:** `{ticket['username']}`\n"
            f"**Category:** {ticket['category']}\n"
            f"**Session:** `{ticket['id']}`\n"
            f"**Support thread:** <#{thread_id}>\n"
            f"**Closed by:** {closed_by}\n\n"
            "The complete transcript is attached below."
        ),
        0xED4245,
    )
    payload["attachments"] = [{"id": 0, "filename": filename, "description": "IZCREAM ticket transcript"}]
    payload["components"].append({"type": 13, "file": {"url": f"attachment://{filename}"}, "spoiler": False})
    response = requests.post(
        f"{DISCORD_API}/channels/{LOG_CHANNEL}/messages",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "User-Agent": "IZCREAM-Vercel/1.0"},
        data={"payload_json": json.dumps(payload)},
        files={"files[0]": (filename, raw, "text/plain")},
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"Transcript upload failed with {response.status_code}: {response.text[:180]}")
    discord("DELETE", f"/channels/{thread_id}")


def json_response(handler: Any, status: int, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Length", str(len(raw)))
    handler.end_headers()
    handler.wfile.write(raw)


def read_json(handler: Any) -> tuple[dict[str, Any], bytes]:
    length = min(int(handler.headers.get("Content-Length") or 0), 32768)
    raw = handler.rfile.read(length) if length else b"{}"
    return json.loads(raw), raw


def same_origin(handler: Any) -> bool:
    origin = handler.headers.get("Origin")
    if not origin:
        return True
    from urllib.parse import urlparse
    return urlparse(origin).netloc == handler.headers.get("Host")
