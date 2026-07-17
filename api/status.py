from http.server import BaseHTTPRequestHandler

from lib.core import BOT_TOKEN, LOG_CHANNEL, SESSION_SECRET, STAFF_ROLE, SUPPORT_CHANNEL, WEBHOOK_URL, json_response


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        json_response(self, 200, {
            "success": True,
            "runtime": "vercel-serverless-python",
            "botTokenConfigured": bool(BOT_TOKEN),
            "channelConfigured": bool(SUPPORT_CHANNEL),
            "logChannelConfigured": bool(LOG_CHANNEL),
            "staffRoleConfigured": bool(STAFF_ROLE),
            "webhookConfigured": bool(WEBHOOK_URL),
            "sessionSecretConfigured": bool(SESSION_SECRET),
            "gatewayStatus": "not-available-on-serverless",
        })
