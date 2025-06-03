"""Test base processsor"""
import pytest
from django.http import HttpRequest

from zeitlabs_payments.providers.base import BaseProcessor  # Replace with the actual import path


@pytest.fixture
def base_processor():
    return BaseProcessor()


def test_payment_view_raises_not_implemented(base_processor):  # pylint: disable=redefined-outer-name
    request = HttpRequest()
    with pytest.raises(NotImplementedError):
        base_processor.payment_view(cart={}, request=request)


def test_get_transaction_parameters_raises_not_implemented(base_processor):  # pylint: disable=redefined-outer-name
    request = HttpRequest()
    with pytest.raises(NotImplementedError):
        base_processor.get_transaction_parameters(cart={}, request=request)
