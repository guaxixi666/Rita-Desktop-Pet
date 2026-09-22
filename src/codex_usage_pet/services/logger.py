from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import log_dir

_SENSITIVE = re.compile(
    r"(?i)(bearer\s+|access[_-]?token[=: ]+|refresh[_-]?token[=: ]+|session[_-]?token[=: ]+)([^\s,;]+)"
)


def redact(text: str) -> str:
    return _SENSITIVE.sub(lambda match: match.group(1) + "[REDACTED]", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            record.args = tuple(redact(str(value)) for value in record.args)
        return True


def configure_logging(directory: Path | None = None) -> Path:
    target = directory or log_dir()
    target.mkdir(parents=True, exist_ok=True)
    log_path = target / "app.log"
    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.addFilter(RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(item, RotatingFileHandler) for item in root.handlers):
        root.addHandler(handler)
    return log_path

