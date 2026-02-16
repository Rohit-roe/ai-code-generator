"""Ollama AI provider client — local LLM inference."""

import asyncio
import json
import re
import httpx
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "deepseek-r1:1.5b"

SYSTEM_MSG = "You are an expert course creator. Return ONLY valid JSON. No preamble. No markdown. No conversational text. Do not explain your response."

BACKSLASH = chr(92)  # The backslash character, avoiding escaping issues


async def check_ollama_health() -> dict:
    """Check if Ollama is running and accessible."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            return {"status": "connected", "url": OLLAMA_BASE_URL}
    except Exception as e:
        logger.error(f"Ollama health check failed: {e}")
        return {"status": "disconnected", "url": OLLAMA_BASE_URL, "error": str(e)}


async def list_models() -> list[dict]:
    """List locally available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            response.raise_for_status()
            data = response.json()
        models = []
        for m in data.get("models", []):
            models.append({
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified_at": m.get("modified_at", ""),
            })
        return models
    except Exception as e:
        logger.error(f"Failed to list Ollama models: {e}")
        return []


async def _make_request_with_retry(client, method, url, **kwargs):
    """Make HTTP request with retry logic."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await getattr(client, method)(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                if attempt == max_retries - 1:
                    logger.error(f"Rate limit exceeded after {max_retries} attempts.")
                    raise
                wait_time = 2 * (attempt + 1)
                logger.warning(f"Rate limited (429). Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                raise


async def call_ollama(model: str | None, prompt: str) -> str:
    """Call Ollama for text generation."""
    model = model or DEFAULT_MODEL
    endpoint = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_MSG},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 32768,
        },
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        logger.info(f"Calling Ollama with model {model}")
        response = await _make_request_with_retry(client, "post", endpoint, json=payload)
        data = response.json()

    content = data["message"]["content"]
    return content


def _unwrap_array(data):
    """If data is a list, return the first dict element."""
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data[0]
    return data


def _is_backslash(ch):
    """Check if a character is a backslash."""
    return ch == BACKSLASH


def _find_last_complete_string_pos(text):
    """Walk through text tracking string boundaries, return position after last closed quote."""
    last_closed_quote = -1
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if _is_backslash(ch):
            escape_next = True
            continue
        if ch == '"':
            if in_string:
                last_closed_quote = i
            in_string = not in_string

    return last_closed_quote


def _find_last_comma_outside_string(text):
    """Find position of last comma that is NOT inside a string."""
    last_comma = -1
    in_string = False
    escape_next = False

    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if _is_backslash(ch):
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
        elif not in_string and ch == ',':
            last_comma = i

    return last_comma


def _close_brackets(text):
    """Close any open brackets and braces."""
    ob = text.count('{') - text.count('}')
    obr = text.count('[') - text.count(']')
    return text + ']' * max(0, obr) + '}' * max(0, ob)


def _try_parse(text):
    """Try to parse JSON, return dict or None."""
    try:
        result = json.loads(text)
        return _unwrap_array(result)
    except (json.JSONDecodeError, ValueError):
        return None


def _try_repair_truncated_json(text):
    """Attempt to repair truncated JSON by closing open brackets/braces."""
    logger.info("Attempting JSON repair on truncated response...")

    # Find the start of JSON
    start = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start = i
            break

    if start < 0:
        logger.warning("No JSON start found in response")
        return None

    text = text[start:]
    logger.info(f"JSON found at pos {start}, total length={len(text)}")

    # === Attempt 0: Close open string (if odd quotes) ===
    # This handles {"key": "val... -> {"key": "val"}
    quote_count = 0
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if _is_backslash(ch):
            escape_next = True
            continue
        if ch == '"':
            quote_count += 1
    
    if quote_count % 2 != 0:
        # Odd number of quotes - try just closing the string
        candidate = text + '"'
        result = _try_parse(_close_brackets(candidate))
        if result:
             logger.info(f"Repair attempt 0 succeeded (closed open string)")
             return result

    # === Attempt 1: Trim to last closed quote, close brackets ===
    last_quote = _find_last_complete_string_pos(text)
    if last_quote > 0:
        candidate = text[:last_quote + 1]
        # Remove dangling key with no value: , "key":
        candidate = re.sub(r',\s*"[^"]*"\s*:\s*$', '', candidate)
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            logger.info(f"Repair attempt 1 succeeded (trimmed to last closed quote)")
            return result

    # === Attempt 2: Trim to last comma outside string ===
    last_comma = _find_last_comma_outside_string(text)
    if last_comma > 0:
        candidate = text[:last_comma]
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            logger.info(f"Repair attempt 2 succeeded (trimmed to last comma)")
            return result

    # === Attempt 3: Trim to last } ===
    last_brace = text.rfind('}')
    if last_brace > 0:
        candidate = text[:last_brace + 1]
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            logger.info(f"Repair attempt 3 succeeded (trimmed to last brace)")
            return result

    # === Attempt 4: Trim to last ] ===
    last_bracket = text.rfind(']')
    if last_bracket > 0:
        candidate = text[:last_bracket + 1]
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            logger.info(f"Repair attempt 4 succeeded (trimmed to last bracket)")
            return result

    logger.error("All JSON repair attempts failed")
    return None


def parse_json_response(text):
    """Parse JSON from AI response, handling common formatting issues."""
    text = text.strip()
    logger.info(f"parse_json_response called, input length={len(text)}")

    # Remove <think>...</think> blocks (deepseek-r1 models)
    # Handle BOTH closed AND unclosed <think> blocks
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    # Handle unclosed <think> (model ran out of tokens during reasoning)
    if '<think>' in text:
        think_pos = text.find('<think>')
        # Everything after <think> until the first { is reasoning text
        json_start = text.find('{', think_pos)
        if json_start >= 0:
            text = text[:think_pos] + text[json_start:]
        else:
            text = text[:think_pos]
        text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Strip any text before the first JSON character
    json_start = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            json_start = i
            break

    if json_start > 0:
        logger.info(f"Stripping {json_start} chars of preamble before JSON")
        text = text[json_start:]
    elif json_start < 0:
        raise ValueError(f"No JSON found in AI response: {text[:200]}...")

    # Try direct parse first
    result = _try_parse(text)
    if result and isinstance(result, dict):
        logger.info("Direct parse succeeded")
        return result

    # The JSON is likely truncated — try repair
    logger.warning(f"Direct parse failed, attempting repair (text length={len(text)})")
    repaired = _try_repair_truncated_json(text)
    if repaired and isinstance(repaired, dict):
        logger.warning("Successfully repaired truncated JSON response")
        return repaired

    raise ValueError(f"Could not parse JSON from AI response: {text[:200]}...")

