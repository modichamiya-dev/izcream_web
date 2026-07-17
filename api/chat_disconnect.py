from http.server import BaseHTTPRequestHandler

from lib.core import clean, discord, event_components, json_response, read_json, read_session, same_origin


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if not same_origin(self):
            json_response(self, 403, {"success": False})
            return
        try:
            body, _ = read_json(self)
            ticket = read_session(body.get("sessionId"))
            if not ticket:
                json_response(self, 200, {"success": True, "notified": False})
                return
            discord("POST", f"/channels/{ticket['threadId']}/messages", event_components(
                "Visitor disconnected",
                f"**{ticket['username']}** left the web chat.\nReason: {clean(body.get('reason'), 160) or 'Page closed'}\nThe thread remains open.",
                0xFEE75C,
            ))
            json_response(self, 200, {"success": True, "notified": True})
        except Exception as error:
            json_response(self, 200, {"success": False, "error": str(error)})
