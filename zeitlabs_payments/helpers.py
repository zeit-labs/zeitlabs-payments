"""Utility functions for the Payfort payment gateway."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin

from zeitlabs_payments.models import Cart

VALID_CURRENCY = 'SAR'


def get_currency(cart: Cart) -> str:
    """
    Return the currency for the given cart.

    :param cart: The shopping cart instance.
    :type cart: Cart
    :raises Exception: If any item in the cart has a currency other than the valid currency.
    :return: The valid currency code.
    :rtype: str
    """
    for item in cart.items.all():
        if item.catalogue_item.currency and item.catalogue_item.currency != VALID_CURRENCY:
            raise Exception(f'Currency not supported: {item.catalogue_item.currency}')
    return VALID_CURRENCY


def get_language(request: Optional[Any]) -> str:
    """
    Return the language code extracted from the request.

    :param request: The request object, expected to have LANGUAGE_CODE attribute.
    :type request: Optional[Any]
    :return: The language code, either 'en' or 'ar', defaults to 'en'.
    :rtype: str
    """
    if request is None or not hasattr(request, 'LANGUAGE_CODE') or not request.LANGUAGE_CODE:
        return 'en'
    result = request.LANGUAGE_CODE.split('-')[0].lower()
    return result if result in ('en', 'ar') else 'en'


def sanitize_text(
    text_to_sanitize: str,
    valid_pattern: str,
    max_length: Optional[int] = None,
    replacement: str = '_',
) -> str:
    """
    Sanitize the input text by replacing invalid characters matching the valid pattern.

    :param text_to_sanitize: The text to sanitize.
    :type text_to_sanitize: str
    :param valid_pattern: The regex pattern of valid characters.
    :type valid_pattern: str
    :param max_length: Maximum length of sanitized text. If None or <=0, no limit.
    :type max_length: Optional[int]
    :param replacement: The replacement character for invalid characters.
    :type replacement: str
    :return: The sanitized text, possibly truncated with ellipsis if too long.
    :rtype: str
    """
    if not valid_pattern:
        return ''

    sanitized = re.sub(valid_pattern, replacement, text_to_sanitize)

    if max_length is None or max_length <= 0:
        return sanitized

    if len(sanitized) > max_length and r'\.' in valid_pattern:
        return sanitized[: max_length - 3] + '...'

    return sanitized[:max_length]


def relative_url_to_absolute_url(
    relative_url: str, request: Any
) -> Optional[str]:
    """
    Convert a relative URL to an absolute URL using request's scheme and site domain.

    :param relative_url: The relative URL to convert.
    :type relative_url: str
    :param request: Django HttpRequest object, expected to have 'scheme' and 'site.domain' attributes.
    :type request: Optional[HttpRequest]
    :return: The absolute URL if conversion is possible, otherwise None.
    :rtype: Optional[str]
    """
    if request and hasattr(request, 'scheme') and hasattr(request, 'site') and request.site:
        return str(urljoin(f'{request.scheme}://{request.site.domain}', relative_url))
    return None
