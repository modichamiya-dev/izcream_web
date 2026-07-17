from http.server import BaseHTTPRequestHandler

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
import requests

from lib.core import DISCORD_API, close_ticket, env, json_response, read_json


PUBLIC_KEY = env("DISCORD_PUBLIC_KEY")


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            body, raw = read_json(self)
            signature = self.headers.get("X-Signature-Ed25519", "")
            timestamp = self.headers.get("X-Signature-Timestamp", "")
            if not PUBLIC_KEY:
                raise RuntimeError("DISCORD_PUBLIC_KEY is not configured")
            VerifyKey(bytes.fromhex(PUBLIC_KEY)).verify(timestamp.encode() + raw, bytes.fromhex(signature))
        except (BadSignatureError, ValueError):
            json_response(self, 401, {"error": "Invalid request signature"})
            return
        except Exception as error:
            json_response(self, 500, {"error": str(error)})
            return

        if body.get("type") == 1:
            json_response(self, 200, {"type": 1})
            return

        data = body.get("data") or {}
        custom_id = str(data.get("custom_id") or "")
        is_button = body.get("type") == 3 and custom_id.startswith("izcream_close:")
        is_command = body.get("type") == 2 and data.get("name") == "close"
        if not is_button and not is_command:
            json_response(self, 200, {"type": 4, "data": {"content": "Unsupported action.", "flags": 64}})
            return

        member = body.get("member") or {}
        user = member.get("user") or body.get("user") or {}
        closed_by = member.get("nick") or user.get("global_name") or user.get("username") or "IZCREAM Staff"
        callback_url = f"{DISCORD_API}/interactions/{body.get('id')}/{body.get('token')}/callback"
        acknowledgement = requests.post(
            callback_url,
            json={"type": 5, "data": {"flags": 64}},
            timeout=2,
        )
        if not acknowledgement.ok:
            json_response(self, 200, {"type": 5, "data": {"flags": 64}})
            return
        try:
            close_ticket(str(body.get("channel_id") or ""), str(closed_by))
            result = "Ticket closed and logged."
        except Exception as error:
            result = f"Could not close ticket: {str(error)[:120]}"
        requests.patch(
            f"{DISCORD_API}/webhooks/{body.get('application_id')}/{body.get('token')}/messages/@original",
            json={"content": result},
            timeout=3,
        )
        self.send_response(204)
        self.end_headers()
