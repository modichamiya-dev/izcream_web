from http.server import BaseHTTPRequestHandler
import traceback
from urllib.parse import parse_qs, urlparse

from lib.core import (
    chat_history, discord, json_response, process_text_close_command,
    read_session, staff_replies, ticket_thread_state,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query)
            ticket = read_session((query.get("sessionId") or [""])[0])
            if not ticket or not ticket.get("threadId"):
                json_response(self, 200, {
                    "success": True,
                    "messages": [],
                    "staffRepliesEnabled": False,
                    "invalidSession": True,
                })
                return
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            state = ticket_thread_state(ticket)
            closed_by = None
            if not state["closed"]:
                closed_by = process_text_close_command(ticket)
                if closed_by:
                    state = {"closed": True, "archived": True}
            if state["archived"] and not state["closed"]:
                discord("PATCH", f"/channels/{ticket['threadId']}", {"archived": False})
                state["archived"] = False
            include_history = (query.get("history") or ["0"])[0] == "1"
            messages = chat_history(ticket) if include_history else staff_replies(ticket, after)
            json_response(self, 200, {
                "success": True,
                "sessionId": (query.get("sessionId") or [""])[0],
                "messages": messages,
                "discordThreadId": ticket["threadId"],
                "staffRepliesEnabled": not state["closed"],
                "closed": state["closed"],
                "closedBy": closed_by,
                "archived": state["archived"],
            })
        except Exception as error:
            traceback.print_exc()
            json_response(self, 502, {"success": False, "error": str(error), "messages": []})
