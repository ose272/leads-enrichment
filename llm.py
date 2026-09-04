"""Local Ollama client. No paid API key is required."""

from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen


PROMPTS = {
    "pitch": """You are writing a first-touch cold email for OSETEK ltd., an AI automation company. Use this foundation and adapt it naturally to the lead's business summary: {summary}. Explain that AI can help the business handle more customers, enquiries, and repetitive tasks without constantly adding staff; respond faster, operate more efficiently, and save time. Keep it under 150 words, warm and clear, without inventing facts or overclaiming. Start with "Hi," or "Hi there," when no first name is explicitly provided. Include a direct WhatsApp call to action using the configured link. End exactly with:\nRegards,\nStephen\nOSETEK ltd.\nOutput only the email body.""",
    "intent": "Classify this reply as exactly one of: curious, objecting, ready-to-talk, neutral. Reply: {reply}",
    "reply": "Write a warm, honest reply under 120 words to this lead message. Address the specific question without overclaiming and invite a next step. Message: {reply}",
    "report": "Given these outreach metrics: {stats}. Write a concise performance summary and suggest 2-3 concrete improvements for next week.",
}


class Ollama:
    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")).rstrip("/")

    def generate(self, prompt: str) -> str:
        request = Request(
            f"{self.base_url}/api/generate",
            data=json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode())
        return str(result.get("response", "")).strip()

    def generate_pitch_email(self, summary: str) -> str:
        return self.generate(PROMPTS["pitch"].format(summary=summary))

    def classify_reply_intent(self, reply: str) -> str:
        result = self.generate(PROMPTS["intent"].format(reply=reply)).lower()
        return next((intent for intent in ("curious", "objecting", "ready-to-talk", "neutral") if intent in result), "neutral")

    def generate_followup_reply(self, reply: str) -> str:
        return self.generate(PROMPTS["reply"].format(reply=reply))

    def generate_weekly_report(self, stats: str) -> str:
        return self.generate(PROMPTS["report"].format(stats=stats))
