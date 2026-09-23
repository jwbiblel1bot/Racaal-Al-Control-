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


# ============================================================
# CORS
# ============================================================

CORS(
    app,
    resources={
        r"/control/*": {
            "origins": [
                "https://racaal-control-center.onrender.com",
                "https://jwbiblel1bot.github.io"
            ]
        },
        r"/health": {
            "origins": [
                "https://racaal-control-center.onrender.com",
                "https://jwbiblel1bot.github.io"
            ]
        }
    }
)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RACAAL Telegram bot -> backend authentication.
# Set the same long random value in Render as RACAAL_BOT_SYNC_SECRET.
RACAAL_BOT_SYNC_SECRET = os.environ.get("RACAAL_BOT_SYNC_SECRET", "")
SETUP_SESSION_MINUTES = int(os.environ.get("RACAAL_SETUP_SESSION_MINUTES", "10"))
RACAAL_CONTROL_CENTER_URL = os.environ.get(
    "RACAAL_CONTROL_CENTER_URL",
    "https://racaal-control-center.onrender.com"
).rstrip("/")


# ============================================================
# SUPABASE CONNECTION
# ============================================================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client | None = None

if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY
        )
        logger.info("Supabase client created successfully.")
    except Exception:
        logger.exception("Failed to create Supabase client.")
        supabase = None
else:
    logger.error(
        "Supabase environment variables are missing. "
        "SUPABASE_URL=%s, SUPABASE_SERVICE_ROLE_KEY=%s",
        bool(SUPABASE_URL),
        bool(SUPABASE_SERVICE_ROLE_KEY)
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

    # Telegram registration is deliberately separate from
    # actual Telegram bot verification.
    "telegram": {
        "registered": False,
        "connection_status": "not_registered",
        "bot_connected": False,
        "bot_is_admin": False,
        "permissions_verified": False,
        "group_title": "",
        "registered_at": None,
    },
}


def default_settings():
    """Return a fresh copy of the default settings."""
    return deepcopy(DEFAULT_SETTINGS)


# ============================================================
# HELPERS
# ============================================================

def valid_telegram_group_id(group_id):
    """
    Validate the normal numeric Telegram group/supergroup ID
    format without claiming that the ID has been verified by
    Telegram itself.
    """
    if not group_id:
        return False

    group_id = str(group_id).strip()

    if not group_id.startswith("-"):
        return False

    numeric_part = group_id[1:]

    return numeric_part.isdigit()


def mark_telegram_registration(settings):
    """
    Add Telegram registration state without removing or
    replacing any existing group settings.
    """
    if not isinstance(settings, dict):
        settings = default_settings()

    settings.setdefault("telegram", {})

    was_registered = bool(
        settings["telegram"].get("registered", False)
    )

    settings["telegram"].update({
        "registered": True,
        "connection_status": "pending_bot_connection",
        "bot_connected": False,
        "bot_is_admin": False,
        "permissions_verified": False,
    })

    if not was_registered and not settings["telegram"].get("registered_at"):
        settings["telegram"]["registered_at"] = (
            datetime.now(timezone.utc).isoformat()
        )

    return settings


# ============================================================
# TELEGRAM <-> RACAAL SECURE CONNECTION HELPERS
# ============================================================

def _bot_sync_authorized():
    """Only the RACAAL Telegram bot may create/update Telegram group records."""
    supplied = request.headers.get("X-RACAAL-BOT-SECRET", "")
    return bool(RACAAL_BOT_SYNC_SECRET) and bool(
        hmac.compare_digest(str(supplied), str(RACAAL_BOT_SYNC_SECRET))
    )


def _setup_token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _setup_session(settings):
    telegram = settings.get("telegram") or {}
    return telegram.get("setup_session") or {}


def _verified_permissions(permissions):
    if not isinstance(permissions, dict):
        return False
    # These are the minimum moderation permissions RACAAL uses for a
    # connected group. Telegram may omit optional permissions.
    return bool(
        permissions.get("can_delete_messages", False)
        and permissions.get("can_restrict_members", False)
    )


def _group_payload(group_id, settings):
    telegram = settings.get("telegram") or {}
    subscription = settings.get("subscription") or {}
    return {
        "group_id": str(group_id),
        "group_title": telegram.get("group_title") or "Telegram Group",
        "chat_type": telegram.get("chat_type") or "supergroup",
        "registered": bool(telegram.get("registered", False)),
        "connection_status": telegram.get("connection_status", "not_registered"),
        "bot_connected": bool(telegram.get("bot_connected", False)),
        "bot_is_admin": bool(telegram.get("bot_is_admin", False)),
        "permissions_verified": bool(telegram.get("permissions_verified", False)),
        "permissions": telegram.get("permissions") or {},
        "registered_at": telegram.get("registered_at"),
        "connected_at": telegram.get("connected_at"),
        "connected_by_user_id": telegram.get("connected_by_user_id"),
        "plan": subscription.get("plan", "trial"),
        "trial_enabled": bool(subscription.get("trial_enabled", True)),
        "trial_days": subscription.get("trial_days", 30),
        "trial_status": subscription.get("status", "trial"),
    }


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    return jsonify({
        "service": "Racaal AI Control API",
        "status": "online",
        "database": "supabase" if supabase else "not_configured"
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    """
    Check both the application and the actual Supabase connection.
    Does not expose any secret credentials.
    """

    if supabase is None:
        return jsonify({
            "status": "error",
            "service": "racaal-control-api",
            "database": "not_configured"
        }), 500

    try:
        result = (
            supabase
            .table("group_settings")
            .select("group_id")
            .limit(1)
            .execute()
        )

        return jsonify({
            "status": "ok",
            "service": "racaal-control-api",
            "database": "connected",
            "database_test": "passed",
            "rows_checked": len(result.data or [])
        })

    except Exception as exc:
        logger.exception("Supabase health check failed.")

        return jsonify({
            "status": "error",
            "service": "racaal-control-api",
            "database": "connection_failed",
            "details": str(exc)
        }), 500


# ============================================================
# GET GROUP SETTINGS
# ============================================================

@app.get("/control/groups/<path:group_id>/settings")
def get_group_settings(group_id):

    group_id = str(group_id).strip()

    logger.info(
        "GET group settings requested for group_id=%s",
        group_id
    )

    if supabase is None:
        logger.error(
            "GET group settings failed because Supabase is not configured."
        )

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

        if not rows:
            logger.info(
                "No settings found for group_id=%s. "
                "Creating default settings.",
                group_id
            )

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
                logger.error(
                    "Default settings could not be created "
                    "for group_id=%s",
                    group_id
                )

                return jsonify({
                    "error": "Could not create default group settings."
                }), 500

            logger.info(
                "Default settings created successfully "
                "for group_id=%s",
                group_id
            )

            return jsonify({
                "group_id": group_id,
                "settings": settings
            })

        logger.info(
            "Existing settings loaded successfully "
            "for group_id=%s",
            group_id
        )

        return jsonify({
            "group_id": group_id,
            "settings": rows[0]["settings"]
        })

    except Exception as exc:
        logger.exception(
            "GET group settings failed for group_id=%s",
            group_id
        )

        return jsonify({
            "error": "Failed to load group settings.",
            "details": str(exc)
        }), 500


# ============================================================
# SAVE GROUP SETTINGS
# ============================================================

@app.put("/control/groups/<path:group_id>/settings")
def save_group_settings(group_id):

    group_id = str(group_id).strip()

    logger.info(
        "SAVE group settings requested for group_id=%s",
        group_id
    )

    if supabase is None:
        logger.error(
            "SAVE group settings failed because Supabase "
            "is not configured."
        )

        return jsonify({
            "error": "Supabase is not configured on the server."
        }), 500

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        logger.warning(
            "SAVE request for group_id=%s contained invalid JSON.",
            group_id
        )

        return jsonify({
            "error": "Request body must be a JSON object."
        }), 400

    settings = data.get("settings")

    if not isinstance(settings, dict):
        logger.warning(
            "SAVE request for group_id=%s is missing "
            "a valid settings object.",
            group_id
        )

        return jsonify({
            "error": "Missing or invalid 'settings' object."
        }), 400

    try:
        result = (
            supabase
            .table("group_settings")
            .upsert(
                {
                    "group_id": group_id,
                    "settings": settings
                },
                on_conflict="group_id"
            )
            .execute()
        )

        if not result.data:
            logger.error(
                "Supabase returned no data after saving "
                "group_id=%s",
                group_id
            )

            return jsonify({
                "error": "Could not save group settings."
            }), 500

        logger.info(
            "Group settings saved successfully "
            "for group_id=%s",
            group_id
        )

        return jsonify({
            "group_id": group_id,
            "settings": settings,
            "message": "Group settings saved permanently."
        })

    except Exception as exc:
        logger.exception(
            "SAVE group settings failed for group_id=%s",
            group_id
        )

        return jsonify({
            "error": "Failed to save group settings.",
            "details": str(exc)
        }), 500


# ============================================================
# TELEGRAM BOT EVENT -> AUTOMATIC GROUP CONNECTION
# ============================================================

@app.post("/control/telegram/bot-sync")
def telegram_bot_sync():
    """
    Trusted endpoint used only by the Telegram bot.

    The bot obtains the real chat ID/name/status from Telegram's
    my_chat_member update and sends that verified event here.
    Customers never call this endpoint directly.
    """
    if not _bot_sync_authorized():
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram bot sync request."
        }), 401

    if supabase is None:
        return jsonify({
            "success": False,
            "error": "Supabase is not configured on the server."
        }), 500

    data = request.get_json(silent=True) or {}
    group_id = str(
        data.get("chat_id") or data.get("group_id") or ""
    ).strip()
    chat_type = str(data.get("chat_type") or "").strip().lower()
    status = str(data.get("bot_status") or "").strip().lower()
    group_title = str(
        data.get("chat_title") or data.get("group_title") or "Telegram Group"
    ).strip()
    admin_user_id = data.get("telegram_user_id")
    permissions = data.get("permissions") or {}

    if not valid_telegram_group_id(group_id):
        return jsonify({
            "success": False,
            "error": "Telegram bot sync requires the real negative Telegram chat ID."
        }), 400

    if chat_type not in {"group", "supergroup"}:
        return jsonify({
            "success": False,
            "error": "Only Telegram groups and supergroups can be connected."
        }), 400

    if status not in {"member", "administrator"}:
        return jsonify({
            "success": False,
            "error": "RACAAL bot is no longer connected to this group."
        }), 400

    bot_is_admin = status == "administrator"
    permissions_verified = bot_is_admin and _verified_permissions(permissions)

    try:
        existing = (
            supabase.table("group_settings")
            .select("group_id, settings")
            .eq("group_id", group_id)
            .limit(1)
            .execute()
        )
        rows = existing.data or []

        settings = (
            deepcopy(rows[0].get("settings") or {})
            if rows else default_settings()
        )

        settings.setdefault("telegram", {})
        telegram = settings["telegram"]
        now = datetime.now(timezone.utc).isoformat()

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
            "group_title": group_title,
            "chat_type": chat_type,
            "permissions": permissions,
            "connected_at": telegram.get("connected_at") or now,
            "last_verified_at": now,
        })

        if admin_user_id is not None:
            telegram["connected_by_user_id"] = str(admin_user_id)

        result = (
            supabase.table("group_settings")
            .upsert({
                "group_id": group_id,
                "settings": settings
            }, on_conflict="group_id")
            .execute()
        )

        if not result.data:
            return jsonify({
                "success": False,
                "error": "Telegram group could not be saved."
            }), 500

        logger.info(
            "Trusted Telegram sync: %s (%s), bot_admin=%s, permissions=%s",
            group_id, group_title, bot_is_admin, permissions_verified
        )

        return jsonify({
            "success": True,
            "message": "Telegram group detected and synchronized.",
            "group": _group_payload(group_id, settings)
        }), 200

    except Exception as exc:
        logger.exception("Trusted Telegram group sync failed.")
        return jsonify({
            "success": False,
            "error": "Telegram group synchronization failed.",
            "details": str(exc)
        }), 500


@app.post("/control/setup/create")
def create_setup_session():
    """
    Create a short-lived private Control Center session.

    Only the Telegram bot may create this session. The group ID is supplied
    by the bot event, not by the website customer.
    """
    if not _bot_sync_authorized():
        return jsonify({
            "success": False,
            "error": "Unauthorized setup-session request."
        }), 401

    if supabase is None:
        return jsonify({
            "success": False,
            "error": "Supabase is not configured on the server."
        }), 500

    data = request.get_json(silent=True) or {}
    group_id = str(data.get("chat_id") or data.get("group_id") or "").strip()
    telegram_user_id = str(data.get("telegram_user_id") or "").strip()

    if not valid_telegram_group_id(group_id):
        return jsonify({"success": False, "error": "Invalid Telegram group."}), 400
    if not telegram_user_id.isdigit():
        return jsonify({"success": False, "error": "Telegram administrator ID is required."}), 400

    try:
        result = (
            supabase.table("group_settings")
            .select("group_id, settings")
            .eq("group_id", group_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return jsonify({
                "success": False,
                "error": "This Telegram group has not been detected by RACAAL."
            }), 404

        settings = deepcopy(rows[0].get("settings") or {})
        telegram = settings.get("telegram") or {}

        if not telegram.get("bot_connected") or not telegram.get("bot_is_admin"):
            return jsonify({
                "success": False,
                "error": "RACAAL bot must be connected and administrator before setup."
            }), 403

        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=SETUP_SESSION_MINUTES)

        telegram["setup_session"] = {
            "token_hash": _setup_token_hash(token),
            "telegram_user_id": telegram_user_id,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "used_at": None,
        }
        settings["telegram"] = telegram

        saved = (
            supabase.table("group_settings")
            .upsert({
                "group_id": group_id,
                "settings": settings
            }, on_conflict="group_id")
            .execute()
        )
        if not saved.data:
            return jsonify({
                "success": False,
                "error": "Could not create the secure setup session."
            }), 500

        setup_url = (
            f"{RACAAL_CONTROL_CENTER_URL}/setup"
            f"?token={token}"
        )

        return jsonify({
            "success": True,
            "setup_url": setup_url,
            "expires_at": expires_at.isoformat(),
            "expires_in_seconds": SETUP_SESSION_MINUTES * 60,
            "group": _group_payload(group_id, settings),
        }), 200

    except Exception as exc:
        logger.exception("Setup session creation failed.")
        return jsonify({
            "success": False,
            "error": "Could not create setup session.",
            "details": str(exc)
        }), 500


@app.post("/control/setup/verify")
def verify_setup_session():
    """
    Public token exchange used by the Control Center.

    The token is the credential. No group ID is accepted from the browser.
    """
    if supabase is None:
        return jsonify({
            "success": False,
            "error": "Supabase is not configured on the server."
        }), 500

    data = request.get_json(silent=True) or {}
    token = str(data.get("token") or "").strip()
    if not token:
        return jsonify({
            "success": False,
            "error": "Setup token is required."
        }), 400

    try:
        token_hash = _setup_token_hash(token)

        # A token is stored inside the detected group's Telegram settings.
        # Search only the Telegram setup-session fields; no browser-supplied
        # group ID is used.
        result = (
            supabase.table("group_settings")
            .select("group_id, settings")
            .execute()
        )

        now = datetime.now(timezone.utc)
        for row in result.data or []:
            group_id = str(row.get("group_id", "")).strip()
            settings = row.get("settings") or {}
            telegram = settings.get("telegram") or {}
            session = telegram.get("setup_session") or {}

            if not hmac.compare_digest(
                str(session.get("token_hash", "")), token_hash
            ):
                continue

            expires_at_raw = session.get("expires_at")
            if not expires_at_raw:
                continue

            try:
                expires_at = datetime.fromisoformat(
                    expires_at_raw.replace("Z", "+00:00")
                )
            except ValueError:
                continue

            if expires_at <= now:
                return jsonify({
                    "success": False,
                    "error": "This setup link has expired. Ask the Telegram bot for a new setup link."
                }), 410

            if session.get("used_at"):
                return jsonify({
                    "success": False,
                    "error": "This setup link has already been used. Ask the Telegram bot for a new setup link."
                }), 410

            session["used_at"] = now.isoformat()
            telegram["setup_session"] = session
            settings["telegram"] = telegram

            saved = (
                supabase.table("group_settings")
                .upsert({
                    "group_id": group_id,
                    "settings": settings
                }, on_conflict="group_id")
                .execute()
            )

            if not saved.data:
                return jsonify({
                    "success": False,
                    "error": "Could not complete the setup session."
                }), 500

            return jsonify({
                "success": True,
                "group": _group_payload(group_id, settings),
                "settings": settings,
                "message": "Telegram administrator session verified."
            }), 200

        return jsonify({
            "success": False,
            "error": "Invalid or unknown setup token."
        }), 401

    except Exception as exc:
        logger.exception("Setup session verification failed.")
        return jsonify({
            "success": False,
            "error": "Failed to verify setup session.",
            "details": str(exc)
        }), 500


# ============================================================
# REGISTER TELEGRAM GROUP
# ============================================================

@app.post("/control/telegram/register")
def register_telegram_group():

    logger.info("Telegram group registration request received.")

    if supabase is None:
        logger.error(
            "Telegram registration failed because Supabase "
            "is not configured."
        )

        return jsonify({
            "success": False,
            "error": "Supabase is not configured on the server."
        }), 500

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "Request body must be a JSON object."
        }), 400

    # Support the current frontend and future naming variants.
    group_id = (
        data.get("group_id")
        or data.get("telegram_group_id")
        or data.get("id")
    )

    if group_id is None:
        return jsonify({
            "success": False,
            "error": "Telegram Group ID is required."
        }), 400

    group_id = str(group_id).strip()

    if not valid_telegram_group_id(group_id):
        logger.warning(
            "Invalid Telegram group ID received: %s",
            group_id
        )

        return jsonify({
            "success": False,
            "error": (
                "Invalid Telegram Group ID. "
                "A Telegram group ID should normally be a "
                "negative numeric ID such as -1001234567890."
            )
        }), 400

    try:
        existing_result = (
            supabase
            .table("group_settings")
            .select("group_id, settings")
            .eq("group_id", group_id)
            .limit(1)
            .execute()
        )

        existing_rows = existing_result.data or []

        # ----------------------------------------------------
        # New group: create its independent settings.
        # ----------------------------------------------------

        if not existing_rows:

            settings = default_settings()
            settings = mark_telegram_registration(settings)

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
                    "success": False,
                    "error": (
                        "Telegram group registration could "
                        "not be saved."
                    )
                }), 500

            logger.info(
                "Telegram group registered successfully: %s",
                group_id
            )

            return jsonify({
                "success": True,
                "group_id": group_id,
                "registered": True,
                "connection_status": "pending_bot_connection",
                "bot_connected": False,
                "bot_is_admin": False,
                "permissions_verified": False,
                "message": (
                    "Telegram group registered in the "
                    "RACAAL Control Center. "
                    "Bot connection is pending."
                ),
                "next_step": (
                    "Add the RACAAL Telegram bot to the group "
                    "and grant the required administrator "
                    "permissions. Telegram connection "
                    "verification will be completed by the "
                    "Telegram integration."
                ),
                "settings": settings
            }), 200

        # ----------------------------------------------------
        # Existing group: preserve every existing setting.
        # ----------------------------------------------------

        existing_settings = existing_rows[0].get("settings")

        if not isinstance(existing_settings, dict):
            existing_settings = default_settings()

        settings = mark_telegram_registration(
            deepcopy(existing_settings)
        )

        update_result = (
            supabase
            .table("group_settings")
            .upsert(
                {
                    "group_id": group_id,
                    "settings": settings
                },
                on_conflict="group_id"
            )
            .execute()
        )

        if not update_result.data:
            return jsonify({
                "success": False,
                "error": (
                    "Telegram registration could not "
                    "be updated."
                )
            }), 500

        logger.info(
            "Existing Telegram group registration updated: %s",
            group_id
        )

        return jsonify({
            "success": True,
            "group_id": group_id,
            "registered": True,
            "connection_status": "pending_bot_connection",
            "bot_connected": False,
            "bot_is_admin": False,
            "permissions_verified": False,
            "message": (
                "Telegram group is registered in the "
                "RACAAL Control Center. "
                "Bot connection is pending."
            ),
            "next_step": (
                "Add the RACAAL Telegram bot to the group "
                "and grant the required administrator "
                "permissions."
            ),
            "settings": settings
        }), 200

    except Exception as exc:
        logger.exception(
            "Telegram group registration failed "
            "for group_id=%s",
            group_id
        )

        return jsonify({
            "success": False,
            "error": "Telegram group registration failed.",
            "details": str(exc)
        }), 500


# ============================================================
# LIST REGISTERED TELEGRAM GROUPS
# ============================================================

@app.get("/control/telegram/groups")
def list_telegram_groups():
    """Return all Telegram groups registered in RACAAL."""
    logger.info("Registered Telegram groups list requested.")

    if supabase is None:
        return jsonify({
            "success": False,
            "groups": [],
            "error": "Supabase is not configured on the server."
        }), 500

    try:
        result = (
            supabase
            .table("group_settings")
            .select("group_id, settings")
            .execute()
        )

        groups = []

        for row in result.data or []:
            group_id = str(row.get("group_id", "")).strip()
            settings = row.get("settings") or {}
            telegram = settings.get("telegram") or {}

            if not telegram.get("registered", False):
                continue

            subscription = settings.get("subscription") or {}

            groups.append({
                "group_id": group_id,
                "group_title": (
                    telegram.get("group_title")
                    or "Telegram Group"
                ),
                "registered": True,
                "registered_at": telegram.get("registered_at"),
                "connection_status": telegram.get(
                    "connection_status",
                    "not_registered"
                ),
                "bot_connected": bool(
                    telegram.get("bot_connected", False)
                ),
                "bot_is_admin": bool(
                    telegram.get("bot_is_admin", False)
                ),
                "permissions_verified": bool(
                    telegram.get("permissions_verified", False)
                ),
                "plan": subscription.get("plan", "trial")
            })

        groups.sort(key=lambda item: item["group_id"])

        return jsonify({
            "success": True,
            "count": len(groups),
            "groups": groups
        })

    except Exception as exc:
        logger.exception("Failed to load Telegram groups.")

        return jsonify({
            "success": False,
            "groups": [],
            "error": "Failed to load Telegram groups.",
            "details": str(exc)
        }), 500


# ============================================================
# TELEGRAM GROUP STATUS
# ============================================================

@app.get("/control/telegram/<path:group_id>/status")
def telegram_group_status(group_id):

    group_id = str(group_id).strip()

    logger.info(
        "Telegram status requested for group_id=%s",
        group_id
    )

    if supabase is None:
        return jsonify({
            "success": False,
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

        if not rows:
            return jsonify({
                "success": True,
                "group_id": group_id,
                "registered": False,
                "connection_status": "not_registered",
                "bot_connected": False,
                "bot_is_admin": False,
                "permissions_verified": False
            })

        settings = rows[0].get("settings") or {}
        telegram = settings.get("telegram") or {}

        return jsonify({
            "success": True,
            "group_id": group_id,
            "registered": bool(
                telegram.get("registered", False)
            ),
            "connection_status": telegram.get(
                "connection_status",
                "not_registered"
            ),
            "bot_connected": bool(
                telegram.get("bot_connected", False)
            ),
            "bot_is_admin": bool(
                telegram.get("bot_is_admin", False)
            ),
            "permissions_verified": bool(
                telegram.get("permissions_verified", False)
            ),
            "group_title": telegram.get(
                "group_title",
                ""
            )
        })

    except Exception as exc:
        logger.exception(
            "Telegram status lookup failed "
            "for group_id=%s",
            group_id
        )

        return jsonify({
            "success": False,
            "error": "Failed to load Telegram group status.",
            "details": str(exc)
        }), 500


# ============================================================
# LOCAL DEVELOPMENT
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
