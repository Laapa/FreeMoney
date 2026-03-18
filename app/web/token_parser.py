from __future__ import annotations

import json
from typing import Any


def parse_token_json_object(raw_value: str, error_message: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return None, error_message

    if not isinstance(parsed, dict):
        return None, error_message

    return parsed, None
