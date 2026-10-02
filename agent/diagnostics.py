"""Safe diagnostics for failures that may include service credentials."""

import os
import re
import traceback
from collections.abc import Mapping

from agent import config


_SENSITIVE_ENV_NAME = re.compile(r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE)
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
_BEARER_CREDENTIAL = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]+=*")
_URL_CREDENTIAL = re.compile(
    r"(?i)([?&](?:key|api[_-]?key|access[_-]?token|token|password)=)[^&#\s]+"
)
_NAMED_CREDENTIAL = re.compile(
    r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\b\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;}]+)"
)


def _string_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _string_values(nested)


def _configured_secret_values() -> list[str]:
    values = [config.GOOGLE_API_KEY or ""]
    try:
        values.extend(_string_values(config._streamlit_secrets()))
    except Exception:
        # Diagnostics must still be available when Streamlit secrets are unavailable.
        pass
    values.extend(
        value for name, value in os.environ.items()
        if _SENSITIVE_ENV_NAME.search(name) and value
    )
    return sorted({value for value in values if value}, key=len, reverse=True)


def safe_exception_traceback(exc: BaseException) -> str:
    """Format an exception traceback after removing configured and common credentials."""
    formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    for secret in _configured_secret_values():
        formatted = formatted.replace(secret, "[REDACTED]")
    formatted = _GOOGLE_API_KEY.sub("[REDACTED_API_KEY]", formatted)
    formatted = _BEARER_CREDENTIAL.sub(r"\1[REDACTED]", formatted)
    formatted = _URL_CREDENTIAL.sub(r"\1[REDACTED]", formatted)
    return _NAMED_CREDENTIAL.sub(r"\1[REDACTED]", formatted)
