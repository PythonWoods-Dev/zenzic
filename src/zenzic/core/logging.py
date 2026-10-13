# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Logging configuration for Zenzic.

Two distinct logging surfaces:

* **CLI mode** — the CLI sets up a root ``zenzic`` logger backed by
  ``RichHandler`` so that log records are formatted consistently with the
  Rich console used for check output.  Call :func:`setup_cli_logging` once
  at startup (``main.py``) and then use :func:`get_logger` anywhere inside
  the ``zenzic`` package.

* **Plugin mode** — MkDocs owns the logging hierarchy.  The plugin acquires
  ``logging.getLogger("mkdocs.plugins.zenzic")`` directly; this module is
  not involved.  :func:`get_logger` returns a plain ``zenzic`` child logger
  that inherits whatever handlers the host application has attached.
"""

from __future__ import annotations

import atexit
import logging

from rich.console import Console
from rich.logging import RichHandler


LOGGER_NAME = "zenzic"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a ``zenzic[.name]`` logger.

    Args:
        name: Optional sub-name appended after ``"zenzic."``.
              Pass ``__name__`` from the calling module for structured
              namespacing (e.g. ``"zenzic.core.validator"``).

    Returns:
        A :class:`logging.Logger` that is a child of the root ``zenzic``
        logger.  If :func:`setup_cli_logging` has been called, the root
        logger carries a ``RichHandler``; otherwise records propagate to
        whatever the host application has configured.
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)


def setup_cli_logging(level: int = logging.WARNING) -> None:
    """Configure the ``zenzic`` root logger for CLI use.

    Attaches a :class:`~rich.logging.RichHandler` so that log records are
    formatted with Rich markup, consistent with the rest of the CLI output.
    Safe to call multiple times — a second call is a no-op when a
    ``RichHandler`` is already attached.

    Must be called from ``main.py`` before any other Zenzic code runs, and
    must *not* be called from the plugin (MkDocs owns the logging hierarchy
    in that context).

    Args:
        level: Minimum log level to emit (default: ``logging.WARNING``).
               Pass ``logging.DEBUG`` to enable verbose diagnostic output.
    """
    logger = logging.getLogger(LOGGER_NAME)
    if any(isinstance(h, RichHandler | DeferringHandler) for h in logger.handlers):
        return  # already configured

    # stderr, never stdout: a warning written to stdout ahead of `--format json`
    # corrupted the payload every machine consumer parses (measured 2026-09-15
    # for .zenzic.toml, 2026-09-17 for pyproject.toml -- the same code path).
    handler = RichHandler(
        level=level,
        console=Console(stderr=True),
        show_time=False,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
    )
    logger.addHandler(DeferringHandler(handler))
    logger.setLevel(level)
    logger.propagate = False
    atexit.register(release_deferred_logs)


class DeferringHandler(logging.Handler):
    """Hold records until the banner has been printed, then pass them through.

    Configuration loads before any command prints its header, so a warning
    about a misspelled key came out first and above the frame -- the one place
    a reader skips. The handler buffers until :func:`release_deferred_logs`
    is called (by the banner printer, or at exit when no banner is printed),
    then forwards every buffered record and every later one immediately.
    """

    def __init__(self, target: logging.Handler) -> None:
        super().__init__()
        self.target = target
        self.buffer: list[logging.LogRecord] | None = []

    def emit(self, record: logging.LogRecord) -> None:
        if self.buffer is not None:
            self.buffer.append(record)
        else:
            self.target.handle(record)

    def release(self) -> None:
        pending, self.buffer = self.buffer, None
        for record in pending or []:
            self.target.handle(record)


def release_deferred_logs() -> None:
    """Flush the records held back until the banner; a no-op afterwards."""
    for h in logging.getLogger(LOGGER_NAME).handlers:
        if isinstance(h, DeferringHandler):
            h.release()
