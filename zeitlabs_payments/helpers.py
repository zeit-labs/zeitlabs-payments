"""Utility functions for the Payfort payment gateway."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urljoin

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from zeitlabs_payments.exceptions import GatewayError
from zeitlabs_payments.models import Cart, CartItem, CatalogueItem

VALID_CURRENCY = 'SAR'
VALID_PATTERNS = {
    'order_description': r"[^A-Za-z0-9 '/\._\-#:$]",
    'customer_name': r"[^A-Za-z _\\/\-\.']",
}
MAX_ORDER_DESCRIPTION_LENGTH_DEFAULT = 150


def verify_param(param: Any, param_name: str, required_type: Any) -> None:
    """
    Verify a parameter type.

    :param param: The parameter to verify.
    :param param_name: The name of the parameter to be used in the exception message.
    :param required_type: The required type of the parameter.
    :raises GatewayError: If the parameter is None or not of the required type.
    """
    if param is None or not isinstance(param, required_type):
        raise GatewayError(
            f'verify_param failed: {param_name} is required and must be '
            f'({required_type.__name__}), but got ({type(param).__name__})'
        )


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


def get_course_id(item: CartItem) -> Optional[str]:
    """Return the course ID."""
    verify_param(item, 'item', CartItem)
    if item.catalogue_item.type == CatalogueItem.ItemType.PAID_COURSE:
        try:
            course = CourseOverview.objects.get(id=item.catalogue_item.item_ref_id)
        except Exception as exc:
            raise GatewayError(
                f'Unable to get course from catalogue item of type "{CatalogueItem.ItemType.PAID_COURSE}" '
                f'and ref_id: "{item.catalogue_item.item_ref_id}".'
            ) from exc
        return str(course.id)
    raise GatewayError(f'Catalogue Item type: "{item.catalogue_item.type}" not supported.')


def get_order_description(cart: Cart, max_length: int = None) -> str:
    """
    Return the order description for the given cart.

    :param cart: The cart.
    :return: The order description.
    """
    def _get_product_description(item: CartItem) -> str:
        """Return the product description."""
        result = get_course_id(item)
        return result or '-'

    verify_param(cart, 'cart', Cart)
    description = ''
    items = list(cart.items.all())
    max_index = len(items) - 1

    for index, item in enumerate(items):
        description += f"{_get_product_description(item).replace(';', '_') or '-'}"
        if index < max_index:
            description += ' // '

    return sanitize_text(
        description,
        VALID_PATTERNS['order_description'],
        max_length=max_length or MAX_ORDER_DESCRIPTION_LENGTH_DEFAULT,
    )


def get_customer_name(cart: Cart) -> str:
    """
    Return the customer name for the given cart.

    :param cart: The cart.
    :return: The customer name.
    """
    verify_param(cart, 'cart', Cart)

    return sanitize_text(
        cart.user.get_full_name() or 'Name not set',
        VALID_PATTERNS['customer_name'],
        max_length=50,
    )


def get_merchant_reference(site_id: int, cart: Cart) -> str:
    """
    Return the merchant reference for the given cart.

    :param site_id: The site ID.
    :param cart: The cart.
    :return: The merchant reference.
    """
    verify_param(site_id, 'site_id', int)
    verify_param(cart, 'cart', Cart)

    return f'{site_id}-{cart.id}'
