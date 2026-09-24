
import os
import logging
import hashlib
import hmac
import secrets
from copy import deepcopy
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
from supabase import create_client, Client

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("racaal-control-api")

RACAAL_BOT_SYNC_SECRET = os.environ.get("RACAAL_BOT_SYNC_SECRET", "")
SETUP_SESSION_MINUTES = int(os.environ.get("RACAAL_SETUP_SESSION_MINUTES", "10"))
CONTROL_SESSION_MINUTES = int(os.environ.get("RACAAL_CONTROL_SESSION_MINUTES", "60"))
CONTROL_CENTER_URL = os.environ.get(
    "RACAAL_CONTROL_CENTER_URL",
    "https://racaal-control-center.onrender.com"
).rstrip("/")
SUPER_ADMIN_IDS = {
    x.strip() for x in os.environ.get("RACAAL_SUPER_ADMIN_IDS", "").split(",")
    if x.strip()
}

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client | None = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

CORS(
    app,
    resources={
        r"/control/*": {
            "origins": [
                "https://racaal-control-center.onrender.com",
                "https://jwbiblel1bot.github.io",
            ]
        },
        r"/health": {"origins": "*"},
    },
)

DEFAULT_SETTINGS = {
    "ai": {
        "enabled": True,
        "assistant_name": "Racaal AI",
        "response_style": "friendly",
        "language": "English",
        "who_can_ask": "everyone",
        "response_length": "medium",
        "typing_indicator": True,
        "customization_enabled": False,
        "custom_prompt": "",
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
    "welcome": {
        "text": "",
        "rules": "",
        "enforce_rules": False,
        "leave_messages": True,
        "photo_verification": False,
        "photo_verification_minutes": 10,
    },
    "automation": {
        "announcements": True,
        "scheduling": True,
        "post_wizard": True,
        "automatic_bible_posts": False,
        "buttons": True,
        "comments": True,
        "comment_url": "",
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
        "expires_at": None,
    },
    "telegram": {
        "registered": False,
        "connection_status": "not_registered",
        "bot_connected": False,
        "bot_is_admin": False,
        "permissions_verified": False,
        "group_title": "",
        "chat_type": "supergroup",
        "permissions": {},
        "registered_at": None,
        "connected_at": None,
        "last_verified_at": None,
        "connected_by_user_id": None,
        "linked_admins": [],
        "setup_session": None,
        "control_sessions": [],
    },
}


def default_settings():
    return deepcopy(DEFAULT_SETTINGS)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def valid_telegram_group_id(group_id):
    value = str(group_id or "").strip()
    return value.startswith("-") and value[1:].isdigit()


def bot_authorized():
    supplied = request.headers.get("X-RACAAL-BOT-SECRET", "")
    return bool(RACAAL_BOT_SYNC_SECRET) and hmac.compare_digest(
        supplied, RACAAL_BOT_SYNC_SECRET
    )


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_group(group_id):
    if supabase is None:
        return None
    result = (
        supabase.table("group_settings")
        .select("group_id, settings")
        .eq("group_id", str(group_id))
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def save_group(group_id, settings):
    return (
        supabase.table("group_settings")
        .upsert(
            {"group_id": str(group_id), "settings": settings},
            on_conflict="group_id",
        )
        .execute()
    )


def ensure_group(group_id):
    row = get_group(group_id)
    if row:
        settings = row.get("settings")
        if not isinstance(settings, dict):
            settings = default_settings()
        return settings
    settings = default_settings()
    save_group(group_id, settings)
    return settings


def session_from_request():
    """
    Read the RACAAL Control Center session token.

    Supports both:
      X-RACAAL-SESSION: <token>
    and:
      Authorization: Bearer <token>
    """
    token = request.headers.get("X-RACAAL-SESSION", "").strip()

    if token:
        return token

    authorization = request.headers.get("Authorization", "").strip()

    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None

    return None


def find_session(session_token):
    if not session_token or supabase is None:
        return None
    wanted = token_hash(session_token)
    result = (
        supabase.table("group_settings")
        .select("group_id, settings")
        .execute()
    )
    for row in result.data or []:
        settings = row.get("settings") or {}
        telegram = settings.get("telegram") or {}
        for item in telegram.get("control_sessions") or []:
            if item.get("token_hash") != wanted:
                continue
            if item.get("revoked_at"):
                continue
            expires = parse_dt(item.get("expires_at"))

            # Permanent Control Center links intentionally have no expiry.
            if not item.get("permanent"):
                if not expires or expires <= datetime.now(timezone.utc):
                    continue

            return {
                "group_id": str(row["group_id"]),
                "user_id": str(item.get("telegram_user_id")),
                "settings": settings,
                "permanent": bool(item.get("permanent")),
            }
    return None


def is_super_admin(user_id):
    return str(user_id) in SUPER_ADMIN_IDS


def authorized_group(group_id, allow_super=True):
    session = find_session(session_from_request())
    if not session:
        return None, (jsonify({"error": "Control Center session is required."}), 401)
    if str(session["group_id"]) == str(group_id):
        return session, None
    if allow_super and is_super_admin(session["user_id"]):
        return session, None
    return None, (jsonify({"error": "You are not authorized to manage this Telegram group."}), 403)


def public_group_payload(group_id, settings):
    t = settings.get("telegram") or {}
    sub = settings.get("subscription") or {}
    return {
        "group_id": str(group_id),
        "group_title": t.get("group_title") or "Telegram Group",
        "chat_type": t.get("chat_type") or "supergroup",
        "registered": bool(t.get("registered")),
        "connection_status": t.get("connection_status", "not_registered"),
        "bot_connected": bool(t.get("bot_connected")),
        "bot_is_admin": bool(t.get("bot_is_admin")),
        "permissions_verified": bool(t.get("permissions_verified")),
        "permissions": t.get("permissions") or {},
        "registered_at": t.get("registered_at"),
        "connected_at": t.get("connected_at"),
        "plan": sub.get("plan", "trial"),
        "status": sub.get("status", "trial"),
        "expires_at": sub.get("expires_at"),
    }


def create_control_session(group_id, user_id, minutes=None, permanent=False):
    """
    Create a Control Center access session.

    Permanent sessions do not expire. The token is still stored only as a
    SHA-256 hash in Supabase. The raw token is returned once so the bot or
    setup flow can place it in the private Control Center link.
    """
    raw = secrets.token_urlsafe(48)

    if permanent:
        expires_at = None
    else:
        minutes = minutes or CONTROL_SESSION_MINUTES
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=minutes)
        ).isoformat()

    settings = ensure_group(group_id)
    telegram = settings.setdefault("telegram", {})

    sessions = []
    for item in telegram.get("control_sessions") or []:
        if item.get("revoked_at"):
            continue

        expires = parse_dt(item.get("expires_at"))

        # Keep permanent sessions and still-valid temporary sessions.
        if item.get("permanent"):
            sessions.append(item)
        elif expires and expires > datetime.now(timezone.utc):
            sessions.append(item)

    sessions.append({
        "token_hash": token_hash(raw),
        "telegram_user_id": str(user_id),
        "created_at": now_iso(),
        "expires_at": expires_at,
        "permanent": bool(permanent),
        "revoked_at": None,
    })

    telegram["control_sessions"] = sessions[-20:]
    save_group(group_id, settings)

    return raw, expires_at


@app.get("/")
def home():
    return jsonify({
        "service": "Racaal AI Control API",
        "status": "online",
        "database": "supabase" if supabase else "not_configured",
    })


@app.get("/health")
def health():
    if supabase is None:
        return jsonify({"status": "error", "database": "not_configured"}), 500
    try:
        supabase.table("group_settings").select("group_id").limit(1).execute()
        return jsonify({
            "status": "ok",
            "service": "racaal-control-api",
            "database": "connected",
            "database_test": "passed",
        })
    except Exception as exc:
        logger.exception("Health check failed")
        return jsonify({
            "status": "error",
            "service": "racaal-control-api",
            "database": "connection_failed",
            "details": str(exc),
        }), 500


@app.post("/control/telegram/bot-sync")
def telegram_bot_sync():
    if not bot_authorized():
        return jsonify({"success": False, "error": "Bot authentication failed."}), 401
    if supabase is None:
        return jsonify({"success": False, "error": "Supabase is not configured."}), 500

    data = request.get_json(silent=True) or {}
    group_id = str(data.get("chat_id") or data.get("group_id") or "").strip()
    if not valid_telegram_group_id(group_id):
        return jsonify({"success": False, "error": "Invalid Telegram group ID."}), 400
    if data.get("chat_type") not in {"group", "supergroup"}:
        return jsonify({"success": False, "error": "Only Telegram groups are supported here."}), 400

    settings = ensure_group(group_id)
    telegram = settings.setdefault("telegram", {})
    permissions = data.get("permissions") or {}
    bot_status = str(data.get("bot_status") or "")
    bot_is_admin = bot_status in {"administrator", "creator"}
    permissions_verified = bool(
        bot_is_admin
        and permissions.get("can_delete_messages")
        and permissions.get("can_restrict_members")
    )

    telegram.update({
        "registered": True,
        "connection_status": (
            "connected" if permissions_verified
            else "permissions_required" if bot_is_admin
            else "bot_member"
        ),
        "bot_connected": True,
        "bot_is_admin": bot_is_admin,
        "permissions_verified": permissions_verified,
        "group_title": str(data.get("chat_title") or "Telegram Group"),
        "chat_type": data.get("chat_type"),
        "permissions": permissions,
        "registered_at": telegram.get("registered_at") or now_iso(),
        "connected_at": telegram.get("connected_at") or now_iso(),
        "last_verified_at": now_iso(),
        "connected_by_user_id": str(data.get("telegram_user_id")) if data.get("telegram_user_id") else telegram.get("connected_by_user_id"),
    })
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "group": public_group_payload(group_id, settings),
    })


@app.post("/control/setup/create")
def setup_create():
    if not bot_authorized():
        return jsonify({"success": False, "error": "Bot authentication failed."}), 401
    data = request.get_json(silent=True) or {}
    group_id = str(data.get("chat_id") or data.get("group_id") or "").strip()
    user_id = str(data.get("telegram_user_id") or "").strip()
    if not valid_telegram_group_id(group_id) or not user_id:
        return jsonify({"success": False, "error": "chat_id and telegram_user_id are required."}), 400

    settings = ensure_group(group_id)
    telegram = settings.setdefault("telegram", {})
    admins = {str(x) for x in (telegram.get("linked_admins") or [])}
    already_linked = user_id in admins

    raw = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=SETUP_SESSION_MINUTES)
    telegram["setup_session"] = {
        "token_hash": token_hash(raw),
        "telegram_user_id": user_id,
        "created_at": now_iso(),
        "expires_at": expires.isoformat(),
        "used_at": None,
    }
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "setup_url": f"{CONTROL_CENTER_URL}/setup?token={raw}",
        "setup_link_type": "one_time",
        "expires_at": expires.isoformat(),
        "returning_admin": already_linked,
        "group": public_group_payload(group_id, settings),
    })


@app.post("/control/setup/verify")
def setup_verify():
    if supabase is None:
        return jsonify({"success": False, "error": "Supabase is not configured."}), 500
    data = request.get_json(silent=True) or {}
    token = str(data.get("token") or "").strip()
    if not token:
        return jsonify({"success": False, "error": "No setup token was provided."}), 400

    wanted = token_hash(token)
    result = supabase.table("group_settings").select("group_id, settings").execute()
    for row in result.data or []:
        settings = row.get("settings") or {}
        telegram = settings.get("telegram") or {}
        session = telegram.get("setup_session") or {}
        if session.get("token_hash") != wanted:
            continue

        expires = parse_dt(session.get("expires_at"))
        if session.get("used_at"):
            return jsonify({"success": False, "error": "This setup link has already been used."}), 410
        if not expires or expires <= datetime.now(timezone.utc):
            return jsonify({"success": False, "error": "This setup link has expired. Ask the RACAAL bot for a new Control Center link."}), 410

        user_id = str(session.get("telegram_user_id") or "")
        group_id = str(row["group_id"])

        admins = {str(x) for x in (telegram.get("linked_admins") or [])}
        admins.add(user_id)
        telegram["linked_admins"] = sorted(admins)
        telegram["setup_session"] = None
        settings["telegram"] = telegram
        save_group(group_id, settings)

        # The setup token is one-time. After successful verification, create
        # a separate permanent Control Center token for this verified admin.
        control_token, control_expires = create_control_session(
            group_id,
            user_id,
            permanent=True,
        )

        control_url = (
            f"{CONTROL_CENTER_URL}/control"
            f"?token={control_token}"
        )

        return jsonify({
            "success": True,
            "group_id": group_id,
            "group": public_group_payload(group_id, settings),
            "session_token": control_token,
            "session_expires_at": None,
            "session_permanent": True,
            "control_url": control_url,
            "message": (
                "Telegram administrator verified. "
                "This group is permanently linked to RACAAL Control Center. "
                "Use the permanent private Control Center link for future access."
            ),
        })

    return jsonify({"success": False, "error": "Invalid or unknown setup token."}), 401



# ============================================================
# CONTROL CENTER OPERATIONAL HELPERS
# ============================================================

def deep_merge_settings(base, updates):
    """Recursively merge a partial settings update into existing settings."""
    if not isinstance(base, dict):
        base = {}
    if not isinstance(updates, dict):
        raise ValueError("Settings must be a JSON object.")

    result = deepcopy(base)

    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge_settings(result[key], value)
        else:
            result[key] = deepcopy(value)

    return result


def get_settings_or_default(group_id):
    row = get_group(group_id)
    if not row:
        return None, None
    settings = row.get("settings") or default_settings()
    if not isinstance(settings, dict):
        settings = default_settings()
    return row, settings


def require_group(group_id):
    if not valid_telegram_group_id(group_id):
        return None, None, (jsonify({
            "success": False,
            "error": "Invalid Telegram group ID."
        }), 400)

    session, error = authorized_group(group_id)
    if error:
        return None, None, error

    row, settings = get_settings_or_default(group_id)
    if not row:
        return None, None, (jsonify({
            "success": False,
            "error": "Telegram group has not been detected by RACAAL."
        }), 404)

    return session, settings, None


def save_merged_settings(group_id, updates):
    """Merge partial settings and persist them without wiping unrelated settings."""
    if not isinstance(updates, dict):
        raise ValueError("Settings must be a JSON object.")

    existing = ensure_group(group_id)
    merged = deep_merge_settings(existing, updates)
    save_group(group_id, merged)
    return merged


def append_setting_item(group_id, section, item):
    row, settings = get_settings_or_default(group_id)
    if not row:
        raise ValueError("Telegram group has not been detected by RACAAL.")

    values = settings.get(section)
    if not isinstance(values, list):
        values = []

    values.append(item)
    settings[section] = values
    save_group(group_id, settings)
    return settings


def remove_setting_item(group_id, section, item_id):
    row, settings = get_settings_or_default(group_id)
    if not row:
        raise ValueError("Telegram group has not been detected by RACAAL.")

    values = settings.get(section)
    if not isinstance(values, list):
        values = []

    settings[section] = [
        item for item in values
        if str(item.get("id")) != str(item_id)
    ]
    save_group(group_id, settings)
    return settings


def telegram_api(method, payload):
    """
    Optional server-side Telegram API integration.

    The website never receives the bot token. The token must be configured
    only as a Render environment variable named TELEGRAM_BOT_TOKEN.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    if not token:
        return {
            "success": False,
            "configured": False,
            "error": "TELEGRAM_BOT_TOKEN is not configured on the RACAAL backend."
        }

    try:
        import requests

        response = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            json=payload,
            timeout=20,
        )
        data = response.json()

        if not response.ok or not data.get("ok"):
            return {
                "success": False,
                "configured": True,
                "error": data.get("description", "Telegram API request failed."),
                "telegram": data,
            }

        return {
            "success": True,
            "configured": True,
            "telegram": data,
        }

    except Exception as exc:
        logger.exception("Telegram API request failed")
        return {
            "success": False,
            "configured": True,
            "error": str(exc),
        }


def validate_button(button):
    if not isinstance(button, dict):
        raise ValueError("Each button must be an object.")

    text = str(button.get("text") or "").strip()
    url = str(button.get("url") or "").strip()

    if not text:
        raise ValueError("Button text is required.")

    if not url.startswith(("https://", "http://", "tg://")):
        raise ValueError("Button URL must start with http://, https://, or tg://.")

    return {
        "text": text,
        "url": url,
    }


def telegram_inline_keyboard(buttons):
    rows = []

    for button in buttons or []:
        if not isinstance(button, dict):
            continue
        text = str(button.get("text") or "").strip()
        url = str(button.get("url") or "").strip()
        if text and url:
            rows.append([{"text": text, "url": url}])

    return rows


def build_message_payload(chat_id, text, buttons=None):
    payload = {
        "chat_id": str(chat_id),
        "text": str(text),
        "disable_web_page_preview": False,
    }

    keyboard = telegram_inline_keyboard(buttons)
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}

    return payload


def now_timestamp():
    return int(datetime.now(timezone.utc).timestamp())


# ============================================================
# OPERATIONAL CONTROL CENTER API
# ============================================================

@app.post("/control/groups/<path:group_id>/control-link/revoke")
def revoke_control_link(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    telegram = settings.get("telegram") or {}
    sessions = telegram.get("control_sessions") or []

    changed = False
    for item in sessions:
        if (
            item.get("permanent")
            and str(item.get("telegram_user_id")) == str(session["user_id"])
            and not item.get("revoked_at")
        ):
            item["revoked_at"] = now_iso()
            changed = True

    if not changed:
        return jsonify({
            "success": False,
            "error": "No active permanent Control Center link was found."
        }), 404

    telegram["control_sessions"] = sessions
    settings["telegram"] = telegram
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "message": "Permanent Control Center link revoked.",
    })


@app.get("/control/groups/<path:group_id>/control")
def control_state(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    telegram = settings.get("telegram") or {}
    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "group_title": telegram.get("group_title"),
        "settings": settings,
        "ai": settings.get("ai") or {},
        "knowledge": settings.get("knowledge") or {},
        "protection": settings.get("protection") or {},
        "management": settings.get("management") or {},
        "welcome": settings.get("welcome") or {},
        "automation": settings.get("automation") or {},
        "members": settings.get("members") or {},
        "analytics": settings.get("analytics") or {},
        "subscription": settings.get("subscription") or {},
        "telegram": telegram,
    })


@app.patch("/control/groups/<path:group_id>/control")
def update_control_state(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    incoming = data.get("settings", data)

    if not isinstance(incoming, dict):
        return jsonify({
            "success": False,
            "error": "Settings must be a JSON object."
        }), 400

    # Never allow group admins to alter Telegram linkage or subscription.
    incoming = deepcopy(incoming)
    incoming.pop("telegram", None)

    if not is_super_admin(session["user_id"]):
        incoming.pop("subscription", None)

    try:
        merged = save_merged_settings(group_id, incoming)
    except Exception as exc:
        logger.exception("Control state update failed")
        return jsonify({
            "success": False,
            "error": "Failed to save Control Center settings.",
            "detail": str(exc),
        }), 500

    return jsonify({
        "success": True,
        "message": "Control Center settings saved successfully.",
        "group_id": str(group_id),
        "settings": merged,
    })


@app.get("/control/groups/<path:group_id>/feature/<path:feature>")
def feature_state(group_id, feature):
    session, settings, error = require_group(group_id)
    if error:
        return error

    if feature not in settings:
        return jsonify({
            "success": False,
            "error": f"Unknown feature: {feature}"
        }), 404

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "feature": feature,
        "settings": settings.get(feature),
    })


@app.put("/control/groups/<path:group_id>/feature/<path:feature>")
def update_feature(group_id, feature):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    feature_settings = data.get("settings", data)

    if not isinstance(feature_settings, dict):
        return jsonify({
            "success": False,
            "error": "Feature settings must be a JSON object."
        }), 400

    if feature in {"telegram", "subscription"} and not is_super_admin(session["user_id"]):
        return jsonify({
            "success": False,
            "error": "This feature is protected."
        }), 403

    try:
        merged = save_merged_settings(
            group_id,
            {feature: feature_settings}
        )
    except Exception as exc:
        logger.exception("Feature update failed")
        return jsonify({
            "success": False,
            "error": "Failed to save feature settings.",
            "detail": str(exc),
        }), 500

    return jsonify({
        "success": True,
        "feature": feature,
        "settings": merged.get(feature) or {},
    })


@app.get("/control/groups/<path:group_id>/overview")
def control_overview(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    telegram = settings.get("telegram") or {}
    automation = settings.get("automation") or {}
    protection = settings.get("protection") or {}
    management = settings.get("management") or {}
    welcome = settings.get("welcome") or {}
    ai = settings.get("ai") or {}

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "group_title": telegram.get("group_title"),
        "telegram": {
            "registered": bool(telegram.get("registered")),
            "bot_connected": bool(telegram.get("bot_connected")),
            "bot_is_admin": bool(telegram.get("bot_is_admin")),
            "permissions_verified": bool(telegram.get("permissions_verified")),
            "connection_status": telegram.get("connection_status"),
        },
        "features": {
            "ai": bool(ai.get("enabled")),
            "scheduling": bool(automation.get("scheduling")),
            "comments": bool(automation.get("comments")),
            "buttons": bool(automation.get("buttons")),
            "announcements": bool(automation.get("announcements")),
            "welcome": bool(management.get("welcome_messages")),
            "rules": bool(management.get("rules_enabled")),
            "photo_verification": bool(welcome.get("photo_verification")),
            "anti_spam": bool(protection.get("anti_spam")),
            "anti_flood": bool(protection.get("anti_flood")),
            "automatic_bible_posts": bool(
                automation.get("automatic_bible_posts")
            ),
        },
    })


# ============================================================
# AI / KNOWLEDGE CONTROL
# ============================================================

@app.get("/control/groups/<path:group_id>/ai")
def get_ai_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "ai": settings.get("ai") or {},
        "knowledge": settings.get("knowledge") or {},
    })


@app.put("/control/groups/<path:group_id>/ai")
def update_ai_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    ai = data.get("ai", {})
    knowledge = data.get("knowledge")

    if not isinstance(ai, dict):
        return jsonify({"success": False, "error": "ai must be an object."}), 400

    updates = {"ai": ai}
    if knowledge is not None:
        if not isinstance(knowledge, dict):
            return jsonify({
                "success": False,
                "error": "knowledge must be an object."
            }), 400
        updates["knowledge"] = knowledge

    merged = save_merged_settings(group_id, updates)

    return jsonify({
        "success": True,
        "ai": merged.get("ai") or {},
        "knowledge": merged.get("knowledge") or {},
    })


@app.post("/control/groups/<path:group_id>/ai/test")
def test_ai_configuration(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    prompt = str(data.get("message") or "").strip()

    if not prompt:
        return jsonify({
            "success": False,
            "error": "A test message is required."
        }), 400

    ai = settings.get("ai") or {}
    if not ai.get("enabled", True):
        return jsonify({
            "success": False,
            "error": "Racaal AI is disabled for this group."
        }), 409

    # The actual AI engine remains the source of generation. This endpoint
    # exposes configuration validation without inventing a second AI engine.
    return jsonify({
        "success": True,
        "ready": True,
        "message": "AI configuration is enabled and ready for the connected RACAAL AI engine.",
        "group_id": str(group_id),
        "prompt": prompt,
        "ai": ai,
        "knowledge": settings.get("knowledge") or {},
    })


# ============================================================
# BUTTONS
# ============================================================

@app.get("/control/groups/<path:group_id>/buttons")
def get_buttons(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    return jsonify({
        "success": True,
        "buttons": (settings.get("automation") or {}).get("buttons_list") or [],
    })


@app.post("/control/groups/<path:group_id>/buttons")
def add_button(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}

    try:
        button = validate_button(data)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    button["id"] = secrets.token_hex(8)
    button["created_at"] = now_iso()

    automation = settings.get("automation") or {}
    buttons = automation.get("buttons_list") or []
    if not isinstance(buttons, list):
        buttons = []

    buttons.append(button)
    automation["buttons_list"] = buttons
    settings["automation"] = automation
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "button": button,
        "buttons": buttons,
    })


@app.delete("/control/groups/<path:group_id>/buttons/<button_id>")
def delete_button(group_id, button_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    buttons = automation.get("buttons_list") or []
    automation["buttons_list"] = [
        item for item in buttons
        if str(item.get("id")) != str(button_id)
    ]
    settings["automation"] = automation
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "buttons": automation["buttons_list"],
    })


# ============================================================
# COMMENTS
# ============================================================

@app.get("/control/groups/<path:group_id>/comments")
def get_comment_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    return jsonify({
        "success": True,
        "comments": {
            "enabled": bool(automation.get("comments")),
            "comment_url": automation.get("comment_url", ""),
            "comment_text": automation.get("comment_text", ""),
            "comment_buttons": automation.get("comment_buttons") or [],
        },
    })


@app.put("/control/groups/<path:group_id>/comments")
def update_comment_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    updates = {
        "comments": bool(data.get("enabled", True)),
        "comment_url": str(data.get("comment_url") or "").strip(),
        "comment_text": str(data.get("comment_text") or ""),
        "comment_buttons": data.get("comment_buttons") or [],
    }

    if updates["comment_url"] and not updates["comment_url"].startswith(
        ("https://", "http://", "tg://")
    ):
        return jsonify({
            "success": False,
            "error": "Comment URL must start with http://, https://, or tg://."
        }), 400

    merged = save_merged_settings(
        group_id,
        {"automation": updates}
    )

    return jsonify({
        "success": True,
        "comments": merged.get("automation") or {},
    })


# ============================================================
# SCHEDULING
# ============================================================

@app.get("/control/groups/<path:group_id>/schedules")
def list_schedules(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    return jsonify({
        "success": True,
        "scheduling_enabled": bool(automation.get("scheduling")),
        "schedules": automation.get("schedules") or [],
    })


@app.post("/control/groups/<path:group_id>/schedules")
def create_schedule(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    if not automation.get("scheduling", True):
        return jsonify({
            "success": False,
            "error": "Scheduling is disabled for this group."
        }), 409

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()

    if not message:
        return jsonify({
            "success": False,
            "error": "Schedule message is required."
        }), 400

    frequency = str(data.get("frequency") or "once").strip().lower()
    allowed = {"once", "daily", "weekly", "monthly", "interval"}
    if frequency not in allowed:
        return jsonify({
            "success": False,
            "error": "Frequency must be once, daily, weekly, monthly, or interval."
        }), 400

    buttons = data.get("buttons") or []
    try:
        clean_buttons = [validate_button(button) for button in buttons]
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    schedule = {
        "id": secrets.token_hex(10),
        "enabled": bool(data.get("enabled", True)),
        "message": message,
        "frequency": frequency,
        "run_at": data.get("run_at"),
        "timezone": data.get("timezone") or "Africa/Kampala",
        "interval_minutes": data.get("interval_minutes"),
        "days": data.get("days") or [],
        "time": data.get("time"),
        "buttons": clean_buttons,
        "created_at": now_iso(),
        "created_by": session["user_id"],
        "last_run_at": None,
        "next_run_at": data.get("run_at"),
    }

    automation["schedules"] = (automation.get("schedules") or []) + [schedule]
    settings["automation"] = automation
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "message": "Schedule saved permanently.",
        "schedule": schedule,
        "schedules": automation["schedules"],
    }), 201


@app.put("/control/groups/<path:group_id>/schedules/<schedule_id>")
def update_schedule(group_id, schedule_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    automation = settings.get("automation") or {}
    schedules = automation.get("schedules") or []

    target = None
    for item in schedules:
        if str(item.get("id")) == str(schedule_id):
            target = item
            break

    if target is None:
        return jsonify({
            "success": False,
            "error": "Schedule not found."
        }), 404

    allowed_keys = {
        "enabled", "message", "frequency", "run_at", "timezone",
        "interval_minutes", "days", "time", "buttons"
    }

    for key in allowed_keys:
        if key in data:
            target[key] = data[key]

    if "buttons" in data:
        try:
            target["buttons"] = [
                validate_button(button) for button in data["buttons"]
            ]
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

    target["updated_at"] = now_iso()
    automation["schedules"] = schedules
    settings["automation"] = automation
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "schedule": target,
    })


@app.delete("/control/groups/<path:group_id>/schedules/<schedule_id>")
def delete_schedule(group_id, schedule_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    schedules = automation.get("schedules") or []

    remaining = [
        item for item in schedules
        if str(item.get("id")) != str(schedule_id)
    ]

    if len(remaining) == len(schedules):
        return jsonify({
            "success": False,
            "error": "Schedule not found."
        }), 404

    automation["schedules"] = remaining
    settings["automation"] = automation
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "message": "Schedule deleted.",
        "schedules": remaining,
    })


# ============================================================
# BROADCASTING
# ============================================================

@app.post("/control/groups/<path:group_id>/broadcast")
def broadcast_message(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    automation = settings.get("automation") or {}
    if not automation.get("announcements", True):
        return jsonify({
            "success": False,
            "error": "Announcements/broadcasting is disabled for this group."
        }), 409

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()

    if not message:
        return jsonify({
            "success": False,
            "error": "Broadcast message is required."
        }), 400

    try:
        buttons = [
            validate_button(button)
            for button in (data.get("buttons") or [])
        ]
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    result = telegram_api(
        "sendMessage",
        build_message_payload(group_id, message, buttons)
    )

    record = {
        "id": secrets.token_hex(10),
        "message": message,
        "buttons": buttons,
        "created_at": now_iso(),
        "created_by": session["user_id"],
        "delivery": "sent" if result.get("success") else "queued",
        "telegram_result": result,
    }

    history = automation.get("broadcast_history") or []
    automation["broadcast_history"] = (history + [record])[-100:]
    settings["automation"] = automation
    save_group(group_id, settings)

    if not result.get("success"):
        return jsonify({
            "success": False,
            "message": "Broadcast was saved, but Telegram delivery is not currently available.",
            "broadcast": record,
        }), 503

    return jsonify({
        "success": True,
        "message": "Broadcast sent to Telegram.",
        "broadcast": record,
    })


@app.post("/control/groups/<path:group_id>/broadcast/schedule")
def schedule_broadcast(group_id):
    data = request.get_json(silent=True) or {}
    data["frequency"] = data.get("frequency") or "once"

    # Reuse the persistent scheduler representation.
    with app.test_request_context(
        json=data,
        headers={
            "Authorization": request.headers.get("Authorization", ""),
            "X-RACAAL-SESSION": request.headers.get("X-RACAAL-SESSION", ""),
        }
    ):
        response = create_schedule(group_id)

    return response


# ============================================================
# BOT ACTION QUEUE / POLLING
# ============================================================

@app.get("/control/bot/groups/<path:group_id>/operational-state")
def bot_operational_state(group_id):
    if not bot_authorized():
        return jsonify({
            "success": False,
            "error": "Bot authentication failed."
        }), 401

    row = get_group(group_id)
    if not row:
        return jsonify({
            "success": False,
            "error": "Group is not registered."
        }), 404

    settings = row.get("settings") or default_settings()

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "settings": settings,
        "automation": settings.get("automation") or {},
        "ai": settings.get("ai") or {},
        "knowledge": settings.get("knowledge") or {},
        "protection": settings.get("protection") or {},
        "management": settings.get("management") or {},
        "welcome": settings.get("welcome") or {},
    })


@app.post("/control/bot/groups/<path:group_id>/event")
def bot_event(group_id):
    if not bot_authorized():
        return jsonify({
            "success": False,
            "error": "Bot authentication failed."
        }), 401

    data = request.get_json(silent=True) or {}
    event = str(data.get("event") or "").strip()

    if not event:
        return jsonify({
            "success": False,
            "error": "event is required."
        }), 400

    row = get_group(group_id)
    if not row:
        return jsonify({
            "success": False,
            "error": "Group is not registered."
        }), 404

    settings = row.get("settings") or default_settings()
    analytics = settings.get("analytics") or {}
    events = analytics.get("event_log_entries") or []

    events.append({
        "id": secrets.token_hex(8),
        "event": event,
        "data": data,
        "created_at": now_iso(),
    })

    analytics["event_log_entries"] = events[-500:]
    settings["analytics"] = analytics
    save_group(group_id, settings)

    return jsonify({
        "success": True,
        "recorded": True,
    })


# ============================================================
# WELCOME / RULES / PROTECTION
# ============================================================

@app.get("/control/groups/<path:group_id>/welcome")
def get_welcome_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    return jsonify({
        "success": True,
        "welcome": settings.get("welcome") or {},
        "management": settings.get("management") or {},
    })


@app.put("/control/groups/<path:group_id>/welcome")
def update_welcome_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    welcome = data.get("welcome", data)
    management = data.get("management")

    if not isinstance(welcome, dict):
        return jsonify({
            "success": False,
            "error": "welcome must be an object."
        }), 400

    updates = {"welcome": welcome}
    if management is not None:
        if not isinstance(management, dict):
            return jsonify({
                "success": False,
                "error": "management must be an object."
            }), 400
        updates["management"] = management

    merged = save_merged_settings(group_id, updates)

    return jsonify({
        "success": True,
        "welcome": merged.get("welcome") or {},
        "management": merged.get("management") or {},
    })


@app.get("/control/groups/<path:group_id>/protection")
def get_protection_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    return jsonify({
        "success": True,
        "protection": settings.get("protection") or {},
    })


@app.put("/control/groups/<path:group_id>/protection")
def update_protection_settings(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Protection settings must be an object."
        }), 400

    merged = save_merged_settings(
        group_id,
        {"protection": data.get("protection", data)}
    )

    return jsonify({
        "success": True,
        "protection": merged.get("protection") or {},
    })


# ============================================================
# ANALYTICS / DASHBOARD DATA
# ============================================================

@app.get("/control/groups/<path:group_id>/analytics")
def group_analytics(group_id):
    session, settings, error = require_group(group_id)
    if error:
        return error

    analytics = settings.get("analytics") or {}
    events = analytics.get("event_log_entries") or []

    counts = {}
    for item in events:
        name = str(item.get("event") or "unknown")
        counts[name] = counts.get(name, 0) + 1

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "analytics": analytics,
        "event_counts": counts,
        "event_count": len(events),
    })


# ============================================================
# SUPER ADMIN GROUP INVENTORY
# ============================================================

@app.get("/control/super-admin/groups")
def super_admin_groups():
    session = find_session(session_from_request())
    if not session:
        return jsonify({
            "success": False,
            "error": "Control Center session is required."
        }), 401

    if not is_super_admin(session["user_id"]):
        return jsonify({
            "success": False,
            "error": "Super Admin access required."
        }), 403

    result = supabase.table("group_settings").select(
        "group_id, settings"
    ).execute()

    groups = []
    for row in result.data or []:
        settings = row.get("settings") or {}
        groups.append(
            public_group_payload(
                str(row["group_id"]),
                settings
            )
        )

    return jsonify({
        "success": True,
        "groups": groups,
        "count": len(groups),
    })


# ============================================================
# END OPERATIONAL CONTROL CENTER API
# ============================================================


@app.post("/control/control-link/verify")
def verify_control_link():
    """
    Verify a permanent Control Center link token and return a usable session.
    The frontend can call this endpoint when it opens with ?token=...
    """
    if supabase is None:
        return jsonify({
            "success": False,
            "error": "Supabase is not configured."
        }), 500

    data = request.get_json(silent=True) or {}
    token = str(data.get("token") or "").strip()

    if not token:
        return jsonify({
            "success": False,
            "error": "No Control Center token was provided."
        }), 400

    session = find_session(token)

    if not session:
        return jsonify({
            "success": False,
            "error": (
                "This Control Center link is invalid or has been revoked. "
                "Ask the RACAAL bot for a new private Control Center link."
            )
        }), 401

    if not session.get("permanent"):
        return jsonify({
            "success": False,
            "error": (
                "This is not a permanent Control Center link."
            )
        }), 401

    group_id = str(session["group_id"])
    row = get_group(group_id)

    if not row:
        return jsonify({
            "success": False,
            "error": "The linked Telegram group could not be found."
        }), 404

    settings = row.get("settings") or default_settings()

    return jsonify({
        "success": True,
        "group_id": group_id,
        "session_token": token,
        "session_permanent": True,
        "session_expires_at": None,
        "group": public_group_payload(group_id, settings),
        "settings": settings,
    })


@app.get("/control/groups/<path:group_id>/settings")
def get_group_settings(group_id):
    if supabase is None:
        return jsonify({"error": "Supabase is not configured."}), 500

    session, error = authorized_group(group_id)
    if error:
        return error

    row = get_group(group_id)
    if not row:
        return jsonify({"error": "Group is not registered."}), 404

    return jsonify({
        "group_id": str(group_id),
        "settings": row.get("settings") or default_settings(),
    })


@app.put("/control/groups/<path:group_id>/settings")
def save_group_settings(group_id):
    if supabase is None:
        return jsonify({"error": "Supabase is not configured."}), 500

    session, error = authorized_group(group_id)
    if error:
        return error

    data = request.get_json(silent=True) or {}
    settings = data.get("settings")

    if not isinstance(settings, dict):
        return jsonify({
            "error": "Missing or invalid settings object."
        }), 400

    existing = get_group(group_id)
    existing_settings = (
        (existing or {}).get("settings")
        or default_settings()
    )

    incoming = deepcopy(settings)

    # Telegram linkage can only be changed by the bot-sync process.
    incoming["telegram"] = existing_settings.get("telegram") or {}

    # Group admins cannot grant themselves premium/trial changes.
    if not is_super_admin(session["user_id"]):
        incoming["subscription"] = (
            existing_settings.get("subscription")
            or DEFAULT_SETTINGS["subscription"]
        )

    merged = deep_merge_settings(
        existing_settings,
        incoming
    )

    save_group(group_id, merged)

    return jsonify({
        "group_id": str(group_id),
        "settings": merged,
        "message": "Group settings saved permanently.",
    })


@app.get("/control/bot/groups/<path:group_id>/settings")
def bot_group_settings(group_id):
    if not bot_authorized():
        return jsonify({
            "success": False,
            "error": "Bot authentication failed."
        }), 401

    row = get_group(group_id)
    if not row:
        return jsonify({
            "success": False,
            "error": "Group is not registered."
        }), 404

    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "settings": row.get("settings") or default_settings(),
    })


@app.get("/control/telegram/groups")
def telegram_groups():
    session = find_session(session_from_request())

    if not session:
        return jsonify({
            "success": False,
            "error": "Control Center session is required."
        }), 401

    result = supabase.table(
        "group_settings"
    ).select("group_id, settings").execute()

    groups = []

    for row in result.data or []:
        settings = row.get("settings") or {}
        telegram = settings.get("telegram") or {}
        admins = {
            str(x)
            for x in (telegram.get("linked_admins") or [])
        }

        if (
            is_super_admin(session["user_id"])
            or session["user_id"] in admins
        ):
            groups.append(
                public_group_payload(
                    str(row["group_id"]),
                    settings
                )
            )

    groups.sort(
        key=lambda x: (x.get("group_title") or "").lower()
    )

    return jsonify({
        "success": True,
        "groups": groups,
        "count": len(groups),
    })


@app.get("/control/telegram/<path:group_id>/status")
def telegram_group_status(group_id):
    session, error = authorized_group(group_id)
    if error:
        return error

    row = get_group(group_id)

    if not row:
        return jsonify({
            "success": True,
            "group_id": str(group_id),
            "registered": False,
            "connection_status": "not_registered",
        })

    return jsonify({
        "success": True,
        **public_group_payload(
            group_id,
            row.get("settings") or default_settings()
        ),
    })


@app.post("/control/telegram/register")
def legacy_register():
    return jsonify({
        "success": False,
        "error": (
            "Manual Telegram Group ID registration is disabled. "
            "Add the RACAAL bot to the group and use the private setup link."
        ),
    }), 410


@app.get("/control/account")
def account():
    session = find_session(session_from_request())

    if not session:
        return jsonify({
            "error": "Control Center session is required."
        }), 401

    return jsonify({
        "user_id": session["user_id"],
        "is_super_admin": is_super_admin(session["user_id"]),
        "group_id": session["group_id"],
    })


@app.get("/control/permissions")
def permissions():
    session = find_session(session_from_request())

    if not session:
        return jsonify({
            "error": "Control Center session is required."
        }), 401

    return jsonify({
        "user_id": session["user_id"],
        "is_super_admin": is_super_admin(session["user_id"]),
        "group_id": session["group_id"],
        "role": (
            "super_admin"
            if is_super_admin(session["user_id"])
            else "group_admin"
        ),
    })


@app.get("/control/platform/status")
def platform_status():
    session = find_session(session_from_request())

    if not session:
        return jsonify({
            "error": "Control Center session is required."
        }), 401

    return jsonify({
        "service": "RACAAL AI Control Center",
        "status": "online",
        "role": (
            "super_admin"
            if is_super_admin(session["user_id"])
            else "group_admin"
        ),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
