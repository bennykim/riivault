"""Voice-of-customer extraction via Claude (optional).

The network call (``classify_documents``) is separated from the response parser
(``parse_voc_response``) so the parsing logic is unit-testable without an API key.
When ``ANTHROPIC_API_KEY`` is unset the whole step is skipped by the caller.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..config import Settings

logger = logging.getLogger("riivault.voc")

VOC_KINDS = {"pain_point", "feature_request", "switch_intent", "bug", "praise"}

_PROMPT = """You classify founder/user feedback mined from public discussions.
For EACH input document decide whether it expresses one of these kinds:
pain_point, feature_request, switch_intent, bug, praise.
If a document expresses none of them, omit it entirely.
Return ONLY a JSON array (no prose, no markdown fences). Each element is:
{"index": <int document index>, "kind": "<one label>", "normalized_text": "<one neutral English sentence>", "entity_name": "<product/brand name or null>"}
Documents:
"""


def parse_voc_response(raw: str) -> list[dict[str, Any]]:
    """Parse an LLM response into validated VoC records; invalid items are skipped."""
    data = _extract_json_array(raw)
    if data is None:
        return []
    records: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        text = item.get("normalized_text")
        if kind not in VOC_KINDS:
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        entity_name = item.get("entity_name")
        if not isinstance(entity_name, str) or not entity_name.strip():
            entity_name = None
        else:
            entity_name = entity_name.strip()
        record: dict[str, Any] = {
            "kind": kind,
            "normalized_text": text.strip(),
            "entity_name": entity_name,
        }
        if isinstance(item.get("index"), int):
            record["index"] = item["index"]
        records.append(record)
    return records


def _extract_json_array(raw: str | None) -> list[Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for value in parsed.values():
                if isinstance(value, list):
                    return value
            return [parsed]
    except json.JSONDecodeError:
        pass
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            return None
    return None


async def classify_documents(
    documents: list[str], settings: Settings
) -> list[dict[str, Any]]:
    """Classify a batch of documents via Claude. Returns [] on skip or any failure."""
    if not settings.voc_enabled or not documents:
        return []
    numbered = "\n".join(f"[{i}] {doc}" for i, doc in enumerate(documents))
    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": _PROMPT + numbered}],
        )
        raw = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash pipeline
        logger.warning("VoC classification failed, skipping batch: %s", exc)
        return []
    return parse_voc_response(raw)
