"""Shared helper: parse a JSON object out of an LLM response that may be
wrapped in markdown fences or surrounded by stray prose."""
import json
import re


def parse_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    return json.loads(raw)
