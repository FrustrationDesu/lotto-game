from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from urllib import error, request


@dataclass(slots=True)
class TranscriptionResult:
    text: str
    language: str | None
    duration_seconds: float | None
    provider: str


class TranscriptionConfigError(ValueError):
    """Raised when transcription provider settings are invalid."""


class TranscriptionProviderError(RuntimeError):
    """Raised when upstream provider returns an error."""

    def __init__(self, message: str, *, status_code: int, retryable: bool = False) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


def transcribe_audio(*, filename: str, content_type: str, data: bytes) -> TranscriptionResult:
    provider = os.getenv("TRANSCRIPTION_PROVIDER", "openai").lower()
    if provider != "openai":
        raise TranscriptionConfigError(f"Unsupported transcription provider: {provider}")
    return _transcribe_with_openai(filename=filename, content_type=content_type, data=data)


def _transcribe_with_openai(*, filename: str, content_type: str, data: bytes) -> TranscriptionResult:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise TranscriptionConfigError("OPENAI_API_KEY is not configured")

    model = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/audio/transcriptions"

    form_fields = {
        "model": model,
        "response_format": "verbose_json",
    }
    body, boundary = _encode_multipart(form_fields, "file", filename, content_type, data)

    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    try:
        with request.urlopen(req, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        _handle_http_error(exc)
    except error.URLError as exc:
        raise TranscriptionProviderError(f"Transcription provider unavailable: {exc.reason}", status_code=503, retryable=True) from exc

    return TranscriptionResult(
        text=payload.get("text", ""),
        language=payload.get("language"),
        duration_seconds=payload.get("duration"),
        provider="openai",
    )


def _handle_http_error(exc: error.HTTPError) -> None:
    raw_body = exc.read().decode("utf-8", errors="ignore")
    message = _extract_error_message(raw_body) or "Transcription provider request failed"

    if exc.code == 429:
        raise TranscriptionProviderError(message, status_code=502, retryable=True) from exc
    if exc.code >= 500:
        raise TranscriptionProviderError(message, status_code=503, retryable=True) from exc
    raise TranscriptionProviderError(message, status_code=502) from exc


def _extract_error_message(raw_body: str) -> str | None:
    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body or None

    if isinstance(parsed, dict):
        error_obj = parsed.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str):
                return message
    return None


def _encode_multipart(
    form_fields: dict[str, str],
    file_field_name: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> tuple[bytes, str]:
    boundary = f"----lotto-boundary-{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for key, value in form_fields.items():
        lines.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"),
                b"",
                str(value).encode("utf-8"),
            ]
        )

    lines.extend(
        [
            f"--{boundary}".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field_name}"; '
                f'filename="{filename}"'
            ).encode("utf-8"),
            f"Content-Type: {content_type}".encode("utf-8"),
            b"",
            data,
            f"--{boundary}--".encode("utf-8"),
            b"",
        ]
    )

    return b"\r\n".join(lines), boundary
