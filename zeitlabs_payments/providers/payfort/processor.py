import logging
from typing import Optional, Any
from urllib.parse import urljoin

from django.conf import settings
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers
from zeitlabs_payments.utils import get_currency, get_language
from zeitlabs_payments.providers.base import BaseProcessor
from .helpers import get_order_description, get_merchant_reference, get_customer_name, get_signature

logger = logging.getLogger(__name__)


class PayFort(BaseProcessor):
    """
    PayFort payment processor.

    For reference, see: https://paymentservices-reference.payfort.com/docs/api/build/index.html
    """
    SLUG = 'payfort'
    CHECKOUT_TEXT = _('Checkout with Payfort credit card')
    NAME = 'Payfort'

    def __init__(self) -> None:
        """Initialize the PayFort processor."""
        self.access_code = settings.PAYFORT['access_code']
        self.merchant_identifier = settings.PAYFORT['merchant_identifier']
        self.request_sha_phrase = settings.PAYFORT['request_sha_phrase']
        self.response_sha_phrase = settings.PAYFORT['response_sha_phrase']
        self.sha_method = settings.PAYFORT['sha_method']
        self.redirect_url = settings.PAYFORT['redirect_url']
        self.return_url = urljoin(
            configuration_helpers.get_value('LMS_URL', settings.BASE_URL),
            reverse('zeitlabs_payments:payfort-callback')
        )

    @classmethod
    def get_payment_method_metadata(cls, cart) -> dict:
        """
        Return metadata for frontend display for this payment processor.
        :return: Dictionary with 'slug', 'title', and 'url'
        """
        return {
            'slug': cls.SLUG,
            'title': cls.NAME,
            'checkout_text': cls.CHECKOUT_TEXT,
            'url': reverse('zeitlabs_payments:initiate-payment', kwargs={'provider': cls.SLUG, 'cart_uuid': cart.id})
        }

    def get_transaction_parameters_base(
        self,
        cart: dict,
        request: Optional[HttpRequest] = None
    ) -> dict:
        """
        Generate base parameters required for the transaction signature.
        """
        return {
            'command': 'PURCHASE',
            'access_code': self.access_code,
            'merchant_identifier': self.merchant_identifier,
            'language': get_language(request),
            'merchant_reference': get_merchant_reference(request.site.id, cart),
            'amount': int(round(cart.total * 100, 0)),
            'currency': get_currency(cart),
            'customer_email': cart.user.email,
            'order_description': get_order_description(cart),
            'return_url': self.return_url
        }

    def generate_signature(self, params: dict = None) -> str:
        """
        Generate a signature for the transaction using provided or base parameters.
        """
        return get_signature(
            self.request_sha_phrase,
            self.sha_method,
            params,
        )

    def get_transaction_parameters(
        self,
        cart: dict,
        request: Optional[HttpRequest] = None,
        use_client_side_checkout: bool = False,
        **kwargs: Any
    ) -> dict:
        """
        Build the required parameters for initiating a payment.

        :param cart: The cart details
        :param request: The HTTP request
        :param use_client_side_checkout: Client-side flag (currently unused)
        :param kwargs: Additional arguments
        :return: A dictionary of transaction parameters
        """
        transaction_parameters = self.get_transaction_parameters_base(cart, request)
        transaction_parameters.update({
            'signature': self.generate_signature(transaction_parameters),
            'payment_page_url': self.redirect_url,
            'csrfmiddlewaretoken': get_token(request),
        })

        return transaction_parameters

    def payment_view(
        self,
        cart: dict,
        request: Optional[HttpRequest] = None,
        use_client_side_checkout: bool = False,
        **kwargs: Any
    ) -> HttpResponse:
        """
        Render the payment redirection view.

        :param cart: The cart details
        :param request: The HTTP request
        :param use_client_side_checkout: Client-side flag (currently unused)
        :param kwargs: Additional arguments
        :return: Rendered HTML response to redirect to the payment gateway
        """
        transaction_parameters = self.get_transaction_parameters(
            cart=cart,
            request=request,
            use_client_side_checkout=use_client_side_checkout,
            **kwargs,
        )
        return render(request, 'zeitlabs_payments/processors/payfort.html', {
            'transaction_parameters': transaction_parameters,
        })
