"""Structured logging configuration."""

import logging
import os
import sys


def setup_logging():
    """Configure structured logging for the application.

    LOG_LEVEL env var controls verbosity (default: INFO).
    LOG_FORMAT env var selects format: 'json' for structured output, anything else for human-readable.
    """
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get("LOG_FORMAT", "text")

    if log_format == "json":
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    else:
        fmt = "%(asctime)s %(levelname)-8s %(name)-30s %(message)s"

    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=fmt,
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy libraries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
