from http.server import BaseHTTPRequestHandler
import traceback
from urllib.parse import parse_qs, urlparse

from lib.core import json_response, read_session, staff_replies


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            query = parse_qs(urlparse(self.path).query)
            ticket = read_session((query.get("sessionId") or [""])[0])
            if not ticket or not ticket.get("threadId"):
                json_response(self, 200, {"success": True, "messages": [], "staffRepliesEnabled": False})
                return
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            json_response(self, 200, {
                "success": True,
                "sessionId": (query.get("sessionId") or [""])[0],
                "messages": staff_replies(ticket, after),
                "discordThreadId": ticket["threadId"],
                "staffRepliesEnabled": True,
            })
        except Exception as error:
            traceback.print_exc()
            json_response(self, 502, {"success": False, "error": str(error), "messages": []})
