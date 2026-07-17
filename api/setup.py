from http.server import BaseHTTPRequestHandler

from lib.core import SETUP_SECRET, SUPPORT_CHANNEL, discord, json_response


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if not SETUP_SECRET or self.headers.get("Authorization") != f"Bearer {SETUP_SECRET}":
            json_response(self, 401, {"success": False, "error": "Unauthorized"})
            return
        try:
            channel = discord("GET", f"/channels/{SUPPORT_CHANNEL}")
            bot = discord("GET", "/users/@me")
            command = discord("POST", f"/applications/{bot['id']}/guilds/{channel['guild_id']}/commands", {
                "name": "close",
                "description": "Close and log the current IZCREAM support ticket",
                "type": 1,
                "default_member_permissions": str(1 << 34),
                "dm_permission": False,
            })
            json_response(self, 200, {"success": True, "commandId": command.get("id"), "name": command.get("name")})
        except Exception as error:
            json_response(self, 502, {"success": False, "error": str(error)})
