"""Configure application logging."""
from __future__ import annotations

import logging
import sys


def configure_logging(debug: bool = False) -> None:
    """Set up structured JSON logging for production, plain text for debug."""
    level = logging.DEBUG if debug else logging.INFO

    if debug:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(fmt))
    else:
        from fb.infrastructure.logging.json_formatter import JsonFormatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if debug else logging.WARNING
    )
