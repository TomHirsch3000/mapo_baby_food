#!/usr/bin/env python3
"""
llm.py — Shared local-LLM client (Ollama via the OpenAI-compatible API).

Single home for the client/retry/JSON-parsing logic that used to be duplicated
between process_ai.py and process_food_ai.py.

Public surface:
    get_client(base_url=None, model=None) -> (client, model)
    call_llm(client, model, system, prompt) -> str
    parse_json_response(text) -> dict | None
    ping(base_url=None) -> bool
"""

import json
import os
import re
import time

import requests
from openai import OpenAI

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")


def get_client(base_url=None, model=None):
    """Ollama speaks the OpenAI protocol; api_key is required but ignored."""
    return OpenAI(base_url=base_url or OLLAMA_BASE, api_key="ollama"), (model or DEFAULT_MODEL)


def ping(base_url=None):
    """True if an Ollama server is reachable. Checks the native root, not /v1."""
    root = (base_url or OLLAMA_BASE).rsplit("/v1", 1)[0]
    try:
        return requests.get(f"{root}/api/tags", timeout=5).status_code == 200
    except Exception:
        return False


def call_llm(client, model, system, prompt, temperature=0.1, max_tokens=400, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt
            print(f"  [retry] LLM error ({e}), waiting {wait}s...")
            time.sleep(wait)


def parse_json_response(text):
    """Strip markdown fences and pull the first JSON object out. None on failure."""
    if not text:
        return None
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None
