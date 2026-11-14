"""Shared application exceptions that cross module boundaries."""

from __future__ import annotations


class JobCancelled(Exception):
    """Raised inside a task when its job was cancelled or superseded."""
