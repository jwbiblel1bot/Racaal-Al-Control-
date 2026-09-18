from openai import OpenAI

from .config import OPENAI_API_KEY, AI_MODEL
from .prompts import SYSTEM_PROMPT
from .context import ConversationContext
from .router import route_message
from .safety import validate_input


class AIEngine:
    """Standalone AI engine with no Telegram or WhatsApp dependencies."""

    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.context = ConversationContext()

    def ask(self, user_id: str, message: str) -> str:
        if not validate_input(message):
            return "I could not process that request."

        route = route_message(message)
        instructions = SYSTEM_PROMPT

        if route == "bible":
            instructions += (
                "\nThe user appears to be asking about the Bible. "
                "Prioritize Bible-focused reasoning and relevant references."
            )

        input_items = [{"role": "system", "content": instructions}]
        input_items.extend(self.context.get_history(user_id))
        input_items.append({"role": "user", "content": message})

        try:
            response = self.client.responses.create(
                model=AI_MODEL,
                input=input_items,
            )
            answer = (response.output_text or "").strip()

            if not answer:
                return "Sorry, I did not receive a usable response."

        except Exception as exc:
            print(f"AI error: {exc}")
            return "Sorry, I could not process your request right now."

        self.context.add_message(user_id, "user", message)
        self.context.add_message(user_id, "assistant", answer)

        return answer
