import os
import sys

from flask import Flask, jsonify, request
import requests

# Allow the API to import the central AI Engine
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai_engine.engine import AIEngine


app = Flask(__name__)

# Initialize the central AI Engine
ai_engine = AIEngine()


@app.get("/")
def home():
    return jsonify({
        "name": "Racaal Central API",
        "status": "online",
        "message": "Racaal backend API is running."
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy"
    })


@app.post("/telegram/webhook")
def telegram_webhook():
    update = request.get_json(silent=True) or {}

    message = update.get("message", {})

    chat = message.get("chat", {})
    user = message.get("from", {})

    text = message.get("text")

    if not text:
        return jsonify({"status": "ignored"}), 200

    chat_id = chat.get("id")
    user_id = str(user.get("id", chat_id))

    if not chat_id:
        return jsonify({"status": "ignored"}), 200

    # Ask the central AI Engine
    answer = ai_engine.ask(user_id, text)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not bot_token:
        return jsonify({
            "status": "error",
            "message": "TELEGRAM_BOT_TOKEN is not configured."
        }), 500

    # Show typing while preparing/sending the answer
    telegram_url = (
        f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    )

    try:
        requests.post(
            telegram_url,
            json={
                "chat_id": chat_id,
                "action": "typing"
            },
            timeout=10
        )

        send_message_url = (
            f"https://api.telegram.org/bot{bot_token}/sendMessage"
        )

        response = requests.post(
            send_message_url,
            json={
                "chat_id": chat_id,
                "text": answer
            },
            timeout=30
        )

        response.raise_for_status()

    except Exception as exc:
        print(f"Telegram error: {exc}")
        return jsonify({
            "status": "error",
            "message": "Could not send Telegram response."
        }), 500

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
