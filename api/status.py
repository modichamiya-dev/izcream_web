from http.server import BaseHTTPRequestHandler

from lib.core import (
    BOT_TOKEN, EXPLICIT_SESSION_SECRET, LOG_CHANNEL, SESSION_SECRET, SETUP_SECRET,
    STAFF_ROLE, SUPPORT_CHANNEL, WEBHOOK_URL, env, json_response,
)


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        json_response(self, 200, {
            "success": True,
            "runtime": "vercel-serverless-python",
            "buildVersion": "2026-07-17-resumable-tickets-1",
            "botTokenConfigured": bool(BOT_TOKEN),
            "channelConfigured": bool(SUPPORT_CHANNEL),
            "logChannelConfigured": bool(LOG_CHANNEL),
            "staffRoleConfigured": bool(STAFF_ROLE),
            "webhookConfigured": bool(WEBHOOK_URL),
            "sessionSecretConfigured": bool(SESSION_SECRET),
            "sessionSecretSource": "environment" if EXPLICIT_SESSION_SECRET else ("bot-token-derived" if SESSION_SECRET else "missing"),
            "discordPublicKeyConfigured": bool(env("DISCORD_PUBLIC_KEY")),
            "setupSecretConfigured": bool(SETUP_SECRET),
            "gatewayStatus": "not-available-on-serverless",
        })
