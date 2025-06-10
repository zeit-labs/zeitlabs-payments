"""Test zeitlabse payment helpers"""

from typing import Any, Optional, Union
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from zeitlabs_payments.exceptions import GatewayError
from zeitlabs_payments.helpers import (
    MAX_ORDER_DESCRIPTION_LENGTH_DEFAULT,
    get_course_id,
    get_currency,
    get_customer_name,
    get_language,
    get_merchant_reference,
    get_order_description,
    relative_url_to_absolute_url,
    sanitize_text,
    verify_param,
)
from zeitlabs_payments.models import Cart, CartItem, CatalogueItem

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


@pytest.mark.parametrize(
    'param, param_name, required_type, expected_error, usecase',
    [
        (123, 'amount', int, None, 'Correct type: int'),
        ('test', 'username', str, None, 'Correct type: str'),
        ([1, 2, 3], 'items', list, None, 'Correct type: list'),
        (None, 'amount', int, 'amount is required and must be (int)', 'Param is None'),
        ('123', 'amount', int, 'amount is required and must be (int)', 'Param is str, expected int'),
        ({'key': 'val'}, 'items', list, 'items is required and must be (list)', 'Param is dict, expected list'),
    ],
)
def test_verify_param(
    param: Any,
    param_name: str,
    required_type: type,
    expected_error: Optional[str],
    usecase: str,
) -> None:
    """
    Test verify_param function with various inputs.

    :param param: Parameter value to verify.
    :param param_name: Name of the parameter.
    :param required_type: Expected type of the parameter.
    :param expected_error: Expected error message substring or None.
    :param usecase: Description of the test case.
    :return: None
    """
    if expected_error is None:
        verify_param(param, param_name, required_type)
    else:
        with pytest.raises(GatewayError) as exc_info:
            verify_param(param, param_name, required_type)
        assert expected_error in str(exc_info.value), f'Failed for case: {usecase}.'


@pytest.mark.django_db
@pytest.mark.parametrize(
    'first_name, last_name, expected_result, expect_exception, usecase',
    [
        ('John', 'Doe', 'John Doe', False, 'Normal full name'),
        ('', '', 'Name not set', False, 'Empty full name fallback'),
        ('', None, 'Name not set', False, 'None last name fallback'),
        ('A' * 60, 'B' * 60, 'A' * 47 + '...', False, 'Long full name truncated'),
        (None, None, None, True, 'Cart is None'),
        ('not_a_cart', None, None, True, 'Cart wrong type'),
    ],
)
def test_get_customer_name(
    first_name: Optional[str],
    last_name: Optional[str],
    expected_result: Optional[str],
    expect_exception: bool,
    usecase: str,
) -> None:
    """
    Test get_customer_name with various cart and user name scenarios.

    :param first_name: User's first name.
    :param last_name: User's last name.
    :param expected_result: Expected customer name string or None.
    :param expect_exception: Whether an exception is expected.
    :param usecase: Description of the test case.
    :return: None
    """
    if expect_exception:
        with pytest.raises(GatewayError):
            get_customer_name('not-cart')
    else:
        user = User.objects.create(
            username=f'{first_name}_{last_name}', first_name=first_name or '', last_name=last_name or ''
        )
        cart = Cart.objects.create(user=user)
        result = get_customer_name(cart)
        assert result == expected_result, f'Failed for case: {usecase}.'


@pytest.mark.django_db
@pytest.mark.parametrize(
    'site_id, cart_id, expected_result, expect_exception, usecase',
    [
        (1, 100, '1-100', False, 'Valid site_id and cart'),
        (0, 5, '0-5', False, 'site_id zero valid'),
        ('1', 1, None, True, 'site_id not int'),
        (1, None, None, True, 'cart is None'),
    ],
)
def test_get_merchant_reference(
    site_id: Union[int, str],
    cart_id: Optional[int],
    expected_result: Optional[str],
    expect_exception: bool,
    usecase: str,
) -> None:
    """
    Test get_merchant_reference with different site and cart inputs.

    :param site_id: Site identifier, expected to be int.
    :param cart_id: Cart identifier or None.
    :param expected_result: Expected merchant reference or None.
    :param expect_exception: Whether an exception is expected.
    :param usecase: Description of the test case.
    :return: None
    """
    cart = None
    if cart_id:
        user = User.objects.get(id=3)
        cart = Cart.objects.create(user=user, id=cart_id)

    if expect_exception:
        with pytest.raises(GatewayError):
            get_merchant_reference(site_id, cart)
    else:
        result = get_merchant_reference(site_id, cart)
        assert result == expected_result, f'Failed for case: {usecase}.'


@pytest.mark.django_db
@pytest.mark.parametrize(
    'sku, expect_exception, expected_message_part',
    [
        ('custom-sku-1', False, None),
        ('custom-sku-with_invlaid_ref_id', True, 'Unable to get course'),
        (None, True, 'not supported'),
    ],
)
def test_get_course_id(sku: Optional[str], expect_exception: bool, expected_message_part: Optional[str]) -> None:
    """
    Test get_course_id with various SKU inputs.

    :param sku: SKU string or None.
    :param expect_exception: Whether an exception is expected.
    :param expected_message_part: Substring expected in exception message.
    :return: None
    """
    if not sku:
        item = CatalogueItem.objects.create(sku='abcd', type='unsupported', price=50)
    else:
        item = CatalogueItem.objects.get(sku=sku)

    cart = Cart.objects.create(user=User.objects.get(id=3), status=Cart.Status.PENDING)
    cart_item = CartItem.objects.create(
        catalogue_item=item,
        original_price=item.price,
        final_price=item.price,
        cart=cart,
    )
    if expect_exception:
        with pytest.raises(GatewayError) as excinfo:
            get_course_id(cart_item)
        assert expected_message_part in str(excinfo.value)
    else:
        result = get_course_id(cart_item)
        assert result == 'course-v1:org1+1+1'


@pytest.mark.django_db
def test_get_order_description_multiple_items(base_data: Any) -> None:  # pylint: disable=unused-argument
    """
    Test get_order_description with multiple items in a cart.

    :param base_data: Fixture data for test setup.
    :return: None
    """
    course1 = CatalogueItem.objects.get(sku='custom-sku-1')
    course2 = CatalogueItem.objects.get(sku='custom-sku-2')

    cart = Cart.objects.create(user_id=3, status=Cart.Status.PENDING)
    cart.items.create(
        catalogue_item=course1,
        original_price=course1.price,
        final_price=course1.price
    )
    cart.items.create(
        catalogue_item=course2,
        original_price=course2.price,
        final_price=course2.price
    )

    result = get_order_description(cart)

    expected = f"{course1.item_ref_id.replace('+', '_')} // {course2.item_ref_id.replace('+', '_')}"
    assert expected == result
    assert len(result) <= MAX_ORDER_DESCRIPTION_LENGTH_DEFAULT


@pytest.mark.django_db
def test_get_order_description_invalid_cart():
    """
    Test that get_order_description raises PayFortException when
    called with an invalid cart argument (not a cart object).
    """
    with pytest.raises(GatewayError, match='cart is required and must be'):
        get_order_description('not-cart')
