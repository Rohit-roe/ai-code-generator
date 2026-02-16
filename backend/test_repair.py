"""Quick test of JSON repair on typical truncated responses."""
import json
import re

BACKSLASH = chr(92)

def _is_backslash(ch):
    return ch == BACKSLASH

def _unwrap_array(data):
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data[0]
    return data

def _find_last_complete_string_pos(text):
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
    ob = text.count('{') - text.count('}')
    obr = text.count('[') - text.count(']')
    return text + ']' * max(0, obr) + '}' * max(0, ob)

def _try_parse(text):
    try:
        result = json.loads(text)
        return _unwrap_array(result)
    except (json.JSONDecodeError, ValueError):
        return None

def _try_repair(text):
    start = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start = i
            break
    if start < 0:
        return None
    text = text[start:]

    # Attempt 1: last closed quote
    last_quote = _find_last_complete_string_pos(text)
    if last_quote > 0:
        candidate = text[:last_quote + 1]
        candidate = re.sub(r',\s*"[^"]*"\s*:\s*$', '', candidate)
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            print(f"  Attempt 1 SUCCESS (trim to last closed quote pos={last_quote})")
            return result

    # Attempt 2: last comma
    last_comma = _find_last_comma_outside_string(text)
    if last_comma > 0:
        candidate = text[:last_comma]
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            print(f"  Attempt 2 SUCCESS (trim to last comma pos={last_comma})")
            return result

    # Attempt 3: last }
    last_brace = text.rfind('}')
    if last_brace > 0:
        candidate = text[:last_brace + 1]
        candidate = re.sub(r',\s*$', '', candidate)
        result = _try_parse(_close_brackets(candidate))
        if result:
            print(f"  Attempt 3 SUCCESS (trim to last brace)")
            return result

    return None


# ─── Test Cases ───────────────────────────────────────────────
test_cases = [
    # Case 1: Truncated inside a string in an array
    '{"title": "MERN Stack Mastery", "description": "Master the MERN", "duration_weeks": 26, "prerequisites": ["Basic understa',

    # Case 2: Truncated after a complete key-value pair
    '{"title": "MERN Stack Mastery", "description": "Master the MERN", "duration_weeks": 26, "prerequisite',

    # Case 3: Truncated mid-array with complete elements
    '{"title": "Test", "weeks": [{"week": 1, "title": "Basics", "focus": "theory", "concepts": ["HTML", "CSS"]}, {"week": 2, "title": "Advan',

    # Case 4: Truncated after a number
    '{"title": "Test", "duration_weeks": 26',

    # Case 5: Truncated with nested objects
    '{"title": "Test", "weeks": [{"week": 1, "title": "Intro", "concepts": ["A", "B"]}, {"week": 2, "title": "More',
]

print("=" * 60)
for i, tc in enumerate(test_cases):
    print(f"\nTest {i+1}: {tc[:80]}...")
    result = _try_repair(tc)
    if result:
        print(f"  RESULT: {json.dumps(result, indent=2)[:200]}")
    else:
        print(f"  FAILED - no parse")
    print()
