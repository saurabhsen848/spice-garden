"""Safe diagnostics for failures that may include service credentials."""

import os
import re
import traceback
from collections.abc import Mapping

from agent import config


_SENSITIVE_ENV_NAME = re.compile(
    r"(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|AUTHORIZATION)", re.IGNORECASE
)
_GOOGLE_API_KEY = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")
_OPAQUE_TOKEN = re.compile(
    r"\b(?=[A-Za-z0-9_-]{32,}\b)(?=[A-Za-z0-9_-]*[A-Za-z])"
    r"(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{32,}\b"
)
_BEARER_CREDENTIAL = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/-]+=*")
_AUTHORIZATION_HEADER = re.compile(
    r"(?im)(\bAuthorization\s*[:=]\s*)(?:Bearer\s+|Basic\s+)?[^\r\n,;]+"
)
_URL_CREDENTIAL = re.compile(
    r"(?i)([?&](?:key|api[_-]?key|access[_-]?token|token|password)=)[^&#\s]+"
)
_URL_USERINFO = re.compile(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@")
_NAMED_CREDENTIAL = re.compile(
    r"(?i)(\b(?:google[_-]?api[_-]?key|api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"password|secret|token)\b\s*[:=]\s*)"
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
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield str(value)


def _configured_secret_values() -> list[str]:
    values = [config.GOOGLE_API_KEY or "", config.API_BASE_URL or ""]
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


def redact_diagnostic_text(text: str) -> str:
    """Redact configured secrets and common credential formats from diagnostic text."""
    for secret in _configured_secret_values():
        text = text.replace(secret, "[REDACTED]")
    text = _AUTHORIZATION_HEADER.sub(r"\1[REDACTED]", text)
    text = _GOOGLE_API_KEY.sub("[REDACTED_API_KEY]", text)
    text = _BEARER_CREDENTIAL.sub(r"\1[REDACTED]", text)
    text = _URL_CREDENTIAL.sub(r"\1[REDACTED]", text)
    text = _URL_USERINFO.sub(r"\1[REDACTED]@", text)
    text = _NAMED_CREDENTIAL.sub(r"\1[REDACTED]", text)
    return _OPAQUE_TOKEN.sub("[REDACTED_TOKEN]", text)


def safe_exception_message(exc: BaseException) -> str:
    """Return a short exception summary suitable for temporary, failure-only UI diagnostics."""
    message = redact_diagnostic_text(str(exc))
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__


def safe_exception_traceback(exc: BaseException) -> str:
    """Format an exception traceback after removing configured and common credentials."""
    formatted = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return redact_diagnostic_text(formatted)
