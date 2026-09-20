import os
from copy import deepcopy

from flask import Flask, jsonify, request
from supabase import create_client, Client

app = Flask(__name__)


# ============================================================
# SUPABASE CONNECTION
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client | None = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY
    )


# ============================================================
# DEFAULT GROUP SETTINGS
# ============================================================

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
    """Return a fresh copy of the default settings."""
    return deepcopy(DEFAULT_SETTINGS)


# ============================================================
# HEALTH / HOME
# ============================================================

@app.get("/")
def home():
    return jsonify({
        "service": "Racaal AI Control API",
        "status": "online",
        "database": "supabase" if supabase else "not_configured"
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "racaal-control-api",
        "database": "connected" if supabase else "not_configured"
    })


# ============================================================
# GET GROUP SETTINGS
# ============================================================

@app.get("/control/groups/<path:group_id>/settings")
def get_group_settings(group_id):

    if supabase is None:
        return jsonify({
            "error": "Supabase is not configured on the server."
        }), 500

    try:
        result = (
            supabase
            .table("group_settings")
            .select("group_id, settings")
            .eq("group_id", group_id)
            .limit(1)
            .execute()
        )

        rows = result.data or []

        # ----------------------------------------------------
        # Group does not exist yet.
        # Create it with default settings.
        # ----------------------------------------------------
        if not rows:
            settings = default_settings()

            insert_result = (
                supabase
                .table("group_settings")
                .insert({
                    "group_id": group_id,
                    "settings": settings
                })
                .execute()
            )

            if not insert_result.data:
                return jsonify({
                    "error": "Could not create default group settings."
                }), 500

            return jsonify({
                "group_id": group_id,
                "settings": settings
            })

        # ----------------------------------------------------
        # Existing group.
        # ----------------------------------------------------
        return jsonify({
            "group_id": group_id,
            "settings": rows[0]["settings"]
        })

    except Exception as exc:
        return jsonify({
            "error": "Failed to load group settings.",
            "details": str(exc)
        }), 500


# ============================================================
# SAVE GROUP SETTINGS
# ============================================================

@app.put("/control/groups/<path:group_id>/settings")
def save_group_settings(group_id):

    if supabase is None:
        return jsonify({
            "error": "Supabase is not configured on the server."
        }), 500

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

    try:
        result = (
            supabase
            .table("group_settings")
            .upsert({
                "group_id": group_id,
                "settings": settings
            }, on_conflict="group_id")
            .execute()
        )

        if not result.data:
            return jsonify({
                "error": "Could not save group settings."
            }), 500

        return jsonify({
            "group_id": group_id,
            "settings": settings,
            "message": "Group settings saved permanently."
        })

    except Exception as exc:
        return jsonify({
            "error": "Failed to save group settings.",
            "details": str(exc)
        }), 500


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
