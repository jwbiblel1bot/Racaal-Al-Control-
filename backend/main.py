
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
            if not expires or expires <= datetime.now(timezone.utc):
                continue
            return {
                "group_id": str(row["group_id"]),
                "user_id": str(item.get("telegram_user_id")),
                "settings": settings,
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


def create_control_session(group_id, user_id, minutes=None):
    minutes = minutes or CONTROL_SESSION_MINUTES
    raw = secrets.token_urlsafe(48)
    expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    settings = ensure_group(group_id)
    telegram = settings.setdefault("telegram", {})
    sessions = [
        x for x in (telegram.get("control_sessions") or [])
        if parse_dt(x.get("expires_at")) and parse_dt(x.get("expires_at")) > datetime.now(timezone.utc)
        and not x.get("revoked_at")
    ]
    sessions.append({
        "token_hash": token_hash(raw),
        "telegram_user_id": str(user_id),
        "created_at": now_iso(),
        "expires_at": expires.isoformat(),
        "revoked_at": None,
    })
    telegram["control_sessions"] = sessions[-20:]
    save_group(group_id, settings)
    return raw, expires.isoformat()


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

        control_token, control_expires = create_control_session(group_id, user_id)
        return jsonify({
            "success": True,
            "group_id": group_id,
            "group": public_group_payload(group_id, settings),
            "session_token": control_token,
            "session_expires_at": control_expires,
            "message": "Telegram administrator verified and group permanently linked to RACAAL Control Center.",
        })

    return jsonify({"success": False, "error": "Invalid or unknown setup token."}), 401


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
    return jsonify({"group_id": str(group_id), "settings": row.get("settings") or default_settings()})


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
        return jsonify({"error": "Missing or invalid settings object."}), 400

    # Group admins can edit operational settings, but cannot grant themselves
    # premium/trial or alter the Telegram linkage.
    existing = get_group(group_id)
    existing_settings = (existing or {}).get("settings") or default_settings()
    incoming = deepcopy(settings)
    incoming["telegram"] = existing_settings.get("telegram") or {}
    if not is_super_admin(session["user_id"]):
        incoming["subscription"] = existing_settings.get("subscription") or DEFAULT_SETTINGS["subscription"]

    save_group(group_id, incoming)
    return jsonify({
        "group_id": str(group_id),
        "settings": incoming,
        "message": "Group settings saved permanently.",
    })


@app.get("/control/bot/groups/<path:group_id>/settings")
def bot_group_settings(group_id):
    if not bot_authorized():
        return jsonify({"success": False, "error": "Bot authentication failed."}), 401
    row = get_group(group_id)
    if not row:
        return jsonify({"success": False, "error": "Group is not registered."}), 404
    return jsonify({
        "success": True,
        "group_id": str(group_id),
        "settings": row.get("settings") or default_settings(),
    })


@app.get("/control/telegram/groups")
def telegram_groups():
    session = find_session(session_from_request())
    if not session:
        return jsonify({"success": False, "error": "Control Center session is required."}), 401

    result = supabase.table("group_settings").select("group_id, settings").execute()
    groups = []
    for row in result.data or []:
        settings = row.get("settings") or {}
        telegram = settings.get("telegram") or {}
        admins = {str(x) for x in (telegram.get("linked_admins") or [])}
        if is_super_admin(session["user_id"]) or session["user_id"] in admins:
            groups.append(public_group_payload(str(row["group_id"]), settings))

    groups.sort(key=lambda x: (x.get("group_title") or "").lower())
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
        **public_group_payload(group_id, row.get("settings") or default_settings()),
    })


@app.post("/control/telegram/register")
def legacy_register():
    # Kept for backward compatibility, but no longer permits arbitrary public
    # registration. New groups must be discovered and verified by the bot.
    return jsonify({
        "success": False,
        "error": "Manual Telegram Group ID registration is disabled. Add the RACAAL bot to the group and use the private setup link.",
    }), 410


@app.get("/control/account")
def account():
    session = find_session(session_from_request())
    if not session:
        return jsonify({"error": "Control Center session is required."}), 401
    return jsonify({
        "user_id": session["user_id"],
        "is_super_admin": is_super_admin(session["user_id"]),
        "group_id": session["group_id"],
    })


@app.get("/control/permissions")
def permissions():
    session = find_session(session_from_request())
    if not session:
        return jsonify({"error": "Control Center session is required."}), 401
    return jsonify({
        "user_id": session["user_id"],
        "is_super_admin": is_super_admin(session["user_id"]),
        "group_id": session["group_id"],
        "role": "super_admin" if is_super_admin(session["user_id"]) else "group_admin",
    })


@app.get("/control/platform/status")
def platform_status():
    session = find_session(session_from_request())
    if not session:
        return jsonify({"error": "Control Center session is required."}), 401
    return jsonify({
        "service": "RACAAL AI Control Center",
        "status": "online",
        "role": "super_admin" if is_super_admin(session["user_id"]) else "group_admin",
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
