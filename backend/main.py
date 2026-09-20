import os
from copy import deepcopy

from flask import Flask, jsonify, request

app = Flask(__name__)


# Temporary in-memory settings store.
# We will replace this with Supabase in the next stage.
GROUP_SETTINGS = {}


DEFAULT_SETTINGS = {
    "ai": {
        "enabled": True,
        "assistant_name": "Racaal AI",
        "response_style": "friendly",
        "language": "English",
        "who_can_ask": "everyone",
        "response_length": "medium",
        "typing_indicator": True,
    },
    "knowledge": {
        "bible_mode": True,
        "general_knowledge": True,
        "memory_enabled": True,
        "history_enabled": True,
        "system_instructions": "",
        "custom_knowledge": "",
    },
    "protection": {
        "anti_spam": True,
        "anti_flood": True,
        "captcha": False,
        "message_limit": 10,
        "blacklist": [],
        "whitelist": [],
    },
    "management": {
        "commands_enabled": True,
        "moderation_commands": True,
        "welcome_messages": True,
        "rules_enabled": True,
        "support_mode": True,
        "service_messages": True,
    },
    "automation": {
        "announcements": True,
        "scheduling": True,
        "post_wizard": True,
        "automatic_bible_posts": False,
        "buttons": True,
        "comments": True,
    },
    "members": {
        "member_tracking": True,
        "invitations": True,
        "referrals": False,
        "levels": False,
        "warnings": True,
    },
    "analytics": {
        "chat_statistics": True,
        "ai_usage": True,
        "event_log": True,
        "reports": True,
    },
    "subscription": {
        "plan": "trial",
        "trial_enabled": True,
        "trial_days": 30,
        "status": "trial",
    },
}


def default_settings():
    """Return a fresh copy so groups do not share the same dictionary."""
    return deepcopy(DEFAULT_SETTINGS)


@app.get("/")
def home():
    return jsonify({
        "service": "Racaal AI Control API",
        "status": "online"
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "racaal-control-api"
    })


@app.get("/control/groups/<path:group_id>/settings")
def get_group_settings(group_id):
    if group_id not in GROUP_SETTINGS:
        GROUP_SETTINGS[group_id] = default_settings()

    return jsonify({
        "group_id": group_id,
        "settings": GROUP_SETTINGS[group_id]
    })


@app.put("/control/groups/<path:group_id>/settings")
def save_group_settings(group_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be a JSON object."
        }), 400

    settings = data.get("settings")

    if not isinstance(settings, dict):
        return jsonify({
            "error": "Missing or invalid 'settings' object."
        }), 400

    GROUP_SETTINGS[group_id] = settings

    return jsonify({
        "group_id": group_id,
        "settings": GROUP_SETTINGS[group_id],
        "message": "Group settings saved."
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
