import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MODEL = os.getenv("AI_MODEL")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured.")

if not AI_MODEL:
    raise RuntimeError("AI_MODEL is not configured.")
