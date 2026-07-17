from http.server import BaseHTTPRequestHandler

from lib.core import clean, json_response, open_or_read_ticket, read_json, same_origin, send_visitor, sign_session


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if not same_origin(self):
            json_response(self, 403, {"success": False, "error": "Forbidden origin"})
            return
        try:
            body, _ = read_json(self)
            message = clean(body.get("message"), 1200)
            if not message:
                raise ValueError("Message is required")
            ticket, created = open_or_read_ticket(body)
            send_visitor(ticket["threadId"], ticket["username"], message)
            json_response(self, 200, {
                "success": True,
                "sessionId": sign_session(ticket),
                "discordThreadId": ticket["threadId"],
                "staffRepliesEnabled": True,
                "created": created,
            })
        except ValueError as error:
            json_response(self, 400, {"success": False, "error": str(error)})
        except Exception as error:
            json_response(self, 502, {"success": False, "error": str(error)})
