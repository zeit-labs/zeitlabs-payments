"""Common Settings"""
from __future__ import annotations

from typing import Any


def plugin_settings(settings: Any) -> None:
    """plugin settings"""
    settings.ABC = getattr(
        settings,
        'ABC',
        'xyz'
    )
