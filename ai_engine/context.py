from collections import defaultdict


class ConversationContext:
    def __init__(self, max_messages: int = 12):
        self.max_messages = max_messages
        self.conversations = defaultdict(list)

    def add_message(self, user_id: str, role: str, content: str) -> None:
        history = self.conversations[user_id]
        history.append({"role": role, "content": content})
        self.conversations[user_id] = history[-self.max_messages:]

    def get_history(self, user_id: str):
        return list(self.conversations[user_id])

    def clear(self, user_id: str) -> None:
        self.conversations.pop(user_id, None)
