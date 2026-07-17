from http.server import BaseHTTPRequestHandler
import traceback

from lib.core import CRON_SECRET, json_response, scan_active_threads_for_close


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not CRON_SECRET or self.headers.get("Authorization") != f"Bearer {CRON_SECRET}":
            json_response(self, 401, {"success": False, "error": "Unauthorized"})
            return
        try:
            result = scan_active_threads_for_close()
            json_response(self, 200, {"success": True, **result})
        except Exception as error:
            traceback.print_exc()
            json_response(self, 502, {"success": False, "error": str(error)})
