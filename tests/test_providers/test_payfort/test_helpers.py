"""Test file for zietlabs payments helpers."""
import hashlib
from typing import Any, Dict, Optional, Union

import pytest
from django.contrib.auth import get_user_model

from zeitlabs_payments.models import Cart, CartItem, CatalogueItem
from zeitlabs_payments.providers.payfort.exceptions import PayFortBadSignatureException, PayFortException
from zeitlabs_payments.providers.payfort.helpers import (
    MAX_ORDER_DESCRIPTION_LENGTH,
    get_course_id,
    get_customer_name,
    get_merchant_reference,
    get_order_description,
    get_signature,
    verify_param,
    verify_response_format,
    verify_signature,
)

User = get_user_model()
VALID_RESPONSE: Dict[str, str] = {
    'amount': '150',
    'currency': 'SAR',
    'command': 'PURCHASE',
    'merchant_reference': '1-1',
    'merchant_identifier': 'abcd',
    'status': '14',
    'eci': 'ECOMMERCE',
    'fort_id': '12341',
    'response_code': '14000',
    'signature': 'secretabcd',
}


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
        with pytest.raises(PayFortException) as exc_info:
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
        with pytest.raises(PayFortException):
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
        with pytest.raises(PayFortException):
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
        with pytest.raises(PayFortException) as excinfo:
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
    assert len(result) <= MAX_ORDER_DESCRIPTION_LENGTH


@pytest.mark.django_db
def test_get_order_description_invalid_cart():
    """
    Test that get_order_description raises PayFortException when
    called with an invalid cart argument (not a cart object).
    """
    with pytest.raises(PayFortException, match='cart is required and must be'):
        get_order_description('not-cart')


@pytest.mark.parametrize(
    'sha_phrase, sha_method, params, expected_hash_start, usecase',
    [
        (
            'secret',
            'SHA-256',
            {'Amount': '100', 'Currency': 'USD'},
            hashlib.sha256('secretAmount=100Currency=USDsecret'.encode()).hexdigest(),
            'Valid SHA256 signature'
        ),
        (
            'phrase',
            'SHA-512',
            {'b': '2', 'a': '1'},
            hashlib.sha512('phrasea=1b=2phrase'.encode()).hexdigest(),
            'Valid SHA512 signature with sorted keys'
        ),
    ]
)
def test_get_signature_valid(sha_phrase, sha_method, params, expected_hash_start, usecase):
    """
    Test that get_signature returns the correct hash signature for valid
    inputs with different SHA methods and parameters.
    """
    signature = get_signature(sha_phrase, sha_method, params)
    assert signature == expected_hash_start, f'failed for usecase: {usecase}'


@pytest.mark.parametrize(
    'sha_phrase, sha_method, params, expected_error, usecase',
    [
        ('secret', 'md5', {'Amount': '100'}, 'Unsupported SHA method', 'Unsupported SHA'),
        (None, 'SHA-256', {'Amount': '100'}, 'sha_phrase is required', 'sha_phrase is None'),
        ('secret', None, {'Amount': '100'}, 'sha_method is required', 'sha_method is None'),
        ('secret', 'SHA-256', None, 'transaction_parameters is required', 'params is None'),
        ('secret', 'SHA-256', 'not a dict', 'transaction_parameters is required', 'params wrong type'),
    ]
)
def test_get_signature_invalid(sha_phrase, sha_method, params, expected_error, usecase):
    """
    Test that get_signature raises PayFortException with appropriate
    error messages when called with invalid or missing parameters.
    """
    with pytest.raises(PayFortException) as exc_info:
        get_signature(sha_phrase, sha_method, params)
    assert expected_error in str(exc_info.value), f'Failed for case: {usecase}.'


@pytest.mark.parametrize('modified_response, expected_error, usecase', [
    (
        VALID_RESPONSE, None,
        'Valid response passes'
    ),
    (
        {k: v for k, v in VALID_RESPONSE.items() if k != 'amount'}, 'Missing field in response: amount',
        'Missing amount field'
    ),
    (
        {**VALID_RESPONSE, 'amount': 1000}, 'Invalid field type in response: amount',
        'Amount not str'
    ),
    (
        {**VALID_RESPONSE, 'amount': '-1000'}, 'Invalid amount in response',
        'Negative amount string'
    ),
    (
        {**VALID_RESPONSE, 'amount': '10.5'}, 'Invalid amount in response',
        'Non-integer amount'
    ),
    (
        {**VALID_RESPONSE, 'currency': 'USD'}, 'Invalid currency in response',
        'Wrong currency'
    ),
    (
        {**VALID_RESPONSE, 'command': 'INVALID'}, 'Invalid command in response',
        'Wrong command'
    ),
    (
        {**VALID_RESPONSE, 'merchant_reference': 'abc'}, 'Invalid merchant_reference in response',
        'Bad merchant reference'
    ),
    (
        {**{k: v for k, v in VALID_RESPONSE.items() if k not in ('fort_id', 'eci')}}, 'Unexpected successful payment',
        'Missing fort_id and eci with success'
    ),
    (
        {**{k: v for k, v in VALID_RESPONSE.items() if k not in ('fort_id', 'eci')}, 'status': '00'}, None,
        'Missing fort_id/eci with non-success status'
    )
])
def test_verify_response_format(modified_response, expected_error, usecase):
    """
    Test that verify_response_format validates the response dictionary correctly,
    raising PayFortException for missing or invalid fields, and passes for valid data.
    """
    if expected_error:
        with pytest.raises(PayFortException) as exc_info:
            verify_response_format(modified_response)
        assert expected_error in str(exc_info.value), f'Failed case: {usecase}'
    else:
        verify_response_format(modified_response)  # Should not raise


@pytest.mark.parametrize(
    'data_override, expected_exception, expected_message',
    [
        (
            {},
            PayFortBadSignatureException,
            'Signature not found',
        ),
        (
            {'signature': 'wrong-signature'},
            PayFortBadSignatureException,
            'Response signature mismatch',
        ),
        (
            {'signature': 'whatever'},
            PayFortException,
            'Unsupported SHA method',
        ),
    ]
)
def test_verify_signature_exceptions(data_override, expected_exception, expected_message):
    """
    Test that verify_signature raises the appropriate exceptions when the
    signature is missing, incorrect, or when an unsupported SHA method is used.
    """
    data = {
        'amount': '1000',
        'currency': 'NZD',
        'command': 'PURCHASE',
        'merchant_reference': '1234-5678'
    }
    data.update(data_override)

    if expected_message == 'Unsupported SHA method':
        sha_method = 'unsupported'
    else:
        sha_method = 'SHA-256'

    with pytest.raises(expected_exception) as exc_info:
        verify_signature('secret', sha_method, data)
    assert expected_message in str(exc_info.value)


def test_verify_signature_valid():
    """
    Test that verify_signature succeeds without exception when provided
    with a valid signature and correct data.
    """
    data = {
        'amount': '1000',
        'currency': 'NZD',
        'command': 'PURCHASE',
        'merchant_reference': '1234-5678'
    }
    data['signature'] = get_signature('secret', 'SHA-256', data)
    verify_signature('secret', 'SHA-256', data)
