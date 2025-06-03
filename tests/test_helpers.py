"""Test zeitlabse payment helpers"""

from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from zeitlabs_payments.helpers import get_currency, get_language, relative_url_to_absolute_url, sanitize_text
from zeitlabs_payments.models import Cart, CatalogueItem

User = get_user_model()


@pytest.mark.django_db
def test_get_currency_valid(base_data: None) -> None:  # pylint: disable=unused-argument
    """
    Test get_currency returns correct currency for a valid cart.

    :param base_data: Fixture to load base data (assumed)
    :return: None
    """
    user = User.objects.get(id=3)
    course_item = CatalogueItem.objects.get(sku='custom-sku-1')
    user_cart = Cart.objects.create(user=user, status=Cart.Status.PENDING)
    user_cart.items.create(
        catalogue_item=course_item,
        original_price=course_item.price,
        final_price=course_item.price
    )
    assert get_currency(user_cart) == 'SAR'


@pytest.mark.django_db
def test_get_currency_raises_for_invalid_currency(base_data: None) -> None:  # pylint: disable=unused-argument
    """
    Test get_currency raises Exception for invalid currency.

    :param base_data: Fixture to load base data (assumed)
    :return: None
    """
    user = User.objects.get(id=3)
    course_item = CatalogueItem.objects.get(sku='custom-sku-2')
    user_cart = Cart.objects.create(user=user, status=Cart.Status.PENDING)
    user_cart.items.create(
        catalogue_item=course_item,
        original_price=course_item.price,
        final_price=course_item.price
    )
    with pytest.raises(Exception, match='Currency not supported: invlaid-curr'):
        get_currency(user_cart)


@pytest.mark.parametrize(
    'language_code, expected',
    [
        ('en-us', 'en'),
        ('ar-SA', 'ar'),
        ('fr-FR', 'en'),
        (None, 'en'),
    ]
)
def test_get_language_with_code(language_code: str, expected: str) -> None:
    """
    Test get_language returns expected language from LANGUAGE_CODE.

    :param language_code: The language code from request
    :param expected: Expected normalized language
    :return: None
    """
    request = MagicMock()
    request.LANGUAGE_CODE = language_code
    assert get_language(request) == expected


def test_get_language_missing_attr() -> None:
    """
    Test get_language returns default when LANGUAGE_CODE is missing.

    :return: None
    """
    request = MagicMock()
    del request.LANGUAGE_CODE
    assert get_language(request) == 'en'


@pytest.mark.parametrize(
    'text, pattern, max_len, expected, usecase',
    [
        ('hello@world', r'[^a-zA-Z0-9]', None, 'hello_world',
         'Replaces "@" with underscore when no max length.'),
        ('hello@world.com', r'[^a-zA-Z0-9]', 10, 'hello_worl',
         'Truncates to 10 chars without dot in pattern.'),
        ('hello.world@example.com', r'[^a-zA-Z0-9\.]', 10, 'hello.w...',
         'Truncates with ellipsis if dot allowed in pattern.'),
        ('test', '', 10, '',
         'Returns empty string if pattern is empty.'),
        ('Name: Tehreem Sadat!', r'[^a-zA-Z0-9]', 20, 'Name__Tehreem_Sadat_',
         'Replaces spaces and special chars with underscores.'),
    ],
)
def test_sanitize_text_cases(
    text: str,
    pattern: str,
    max_len: int,
    expected: str,
    usecase: str
) -> None:
    """
    Test sanitize_text with multiple edge cases.

    :param text: Input text
    :param pattern: Regex pattern for invalid chars
    :param max_len: Maximum allowed length
    :param expected: Expected sanitized string
    :param usecase: Description of test case
    :return: None
    """
    result = sanitize_text(text, pattern, max_length=max_len)
    assert result == expected, f'Failed usecase: {usecase}'


@pytest.mark.django_db
def test_relative_url_to_absolute_url_valid() -> None:
    """
    Test relative_url_to_absolute_url returns full URL for valid request.

    :return: None
    """
    request = MagicMock(
        scheme='https',
        site=Site.objects.create(domain='test.com', name='test.com')
    )
    result = relative_url_to_absolute_url('/checkout', request)
    assert result == f'{request.scheme}://{request.site.domain}/checkout'


def test_relative_url_to_absolute_url_missing_site() -> None:
    """
    Test relative_url_to_absolute_url returns None if site is missing.

    :return: None
    """
    request = MagicMock(scheme='https', site=None)
    assert relative_url_to_absolute_url('/checkout', request) is None


def test_relative_url_to_absolute_url_none_request() -> None:
    """
    Test relative_url_to_absolute_url returns None if request is None.

    :return: None
    """
    assert relative_url_to_absolute_url('/checkout', None) is None
