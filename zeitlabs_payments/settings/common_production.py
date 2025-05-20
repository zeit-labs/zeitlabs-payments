"""Common Settings"""
from typing import Any


def plugin_settings(settings: Any) -> None:
    """
    plugin settings
    """
    settings.PAYFORT = getattr(
        settings,
        'PAYFORT',
        {},
    )

    settings.BASE_URL = getattr(
        settings,
        'BASE_URL',
        '',
    )
