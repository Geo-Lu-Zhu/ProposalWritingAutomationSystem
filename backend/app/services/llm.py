"""Thin wrappers around the Mistral and OpenAI chat APIs.

Mirrors the notebook's role split: Mistral does creative generation
(ideas, drafting, revision), OpenAI does NIH-style reviewing/scoring.
Both run in threads via asyncio.to_thread since the underlying HTTP calls
are blocking.
"""
import asyncio
import json
import re

import openai
import requests

from app.config import MISTRAL_API_KEY, MISTRAL_API_URL, MISTRAL_MODEL, OPENAI_API_KEY, OPENAI_MODEL

_openai_client = openai.OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _mistral_chat_sync(messages: list[dict], temperature: float = 0.25, max_tokens: int | None = None) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
    }
    payload = {
        "model": MISTRAL_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(MISTRAL_API_URL, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


async def mistral_chat(messages: list[dict], temperature: float = 0.25, max_tokens: int | None = None) -> str:
    return await asyncio.to_thread(_mistral_chat_sync, messages, temperature, max_tokens)


def _openai_chat_sync(messages: list[dict], temperature: float = 0.0) -> str:
    if _openai_client is None:
        raise RuntimeError("OPENAI_API_KEY is not configured on the server.")
    completion = _openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=temperature,
        messages=messages,
    )
    return completion.choices[0].message.content


async def openai_chat(messages: list[dict], temperature: float = 0.0) -> str:
    return await asyncio.to_thread(_openai_chat_sync, messages, temperature)


def clean_json_text(text: str) -> str:
    """Strip markdown fences / leading commentary and pull out the JSON object."""
    text = text.strip()
    text = text.replace("```json", "```")
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :].strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else text


def safe_json_parse(text: str) -> dict:
    if isinstance(text, dict):
        return text
    if not text:
        return {}
    cleaned = clean_json_text(text)
    try:
        return json.loads(cleaned)
    except Exception:
        return {"raw_text": text, "error": "Could not parse JSON"}
