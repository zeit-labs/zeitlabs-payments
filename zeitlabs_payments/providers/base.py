import hashlib
import logging
from typing import Optional, Any

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class BaseProcessor:
    """Base class for all payment processors."""

    SLUG: str
    NAME: str
    CHECKOUT_TEXT: str
    PAYMENT_INITIALIZATION_URL: str

    def payment_view(
        self,
        cart: dict,
        request: Optional[HttpRequest] = None,
        use_client_side_checkout: bool = False,
        **kwargs: Any
    ) -> HttpResponse:
        """
        Display the payment page for this processor.

        :param cart: The cart object/dictionary
        :param request: The incoming request object
        :param use_client_side_checkout: Flag for client-side checkout
        :param kwargs: Additional parameters
        :return: HTTP response for the payment view
        """
        raise NotImplementedError

    def get_transaction_parameters(
        self,
        cart: dict,
        request: Optional[HttpRequest] = None,
        use_client_side_checkout: bool = False,
        **kwargs: Any
    ) -> dict:
        """
        Generate transaction parameters required by the processor.

        :param cart: The cart object/dictionary
        :param request: The incoming request object
        :param use_client_side_checkout: Flag for client-side checkout
        :param kwargs: Additional parameters
        :return: A dictionary of transaction parameters
        """
        raise NotImplementedError
