"""Porcessors registry"""

from .base import BaseProcessor
from .payfort.processor import PayFort

PROCESSORS = {
    PayFort.SLUG: PayFort
}


def get_processor(slug: str) -> BaseProcessor:
    """
    Return an *instance* of the processor that matches `slug`
    or raise KeyError if unknown.
    """
    try:
        return PROCESSORS[slug]()
    except KeyError as exc:
        raise ValueError(f'Unsupported payment provider: {slug}') from exc
