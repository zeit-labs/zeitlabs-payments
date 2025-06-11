"""Payfort Views"""

import logging
from typing import Any

from django.db import transaction
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from zeitlabs_payments.exceptions import CartFulfillmentError
from zeitlabs_payments.models import Cart, AuditLog
from zeitlabs_payments.providers.payfort.exceptions import PayFortException
from zeitlabs_payments.providers.payfort.helpers import SUCCESS_STATUS, verify_response_format
from zeitlabs_payments.providers.payfort.processor import PayFort

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PayfortFeedbackView(View):
    """
    Callback endpoint for PayFort to notify about payment status.
    """

    @property
    def payment_processor(self) -> PayFort:
        return PayFort()

    def post(self, request: Any) -> None:
        """
        Handle the callback POST request from PayFort.

        :param request: DRF request object
        :return: Rendered invoice page or HTTP response

        TODO: use audit log for everything including failed transaction.
        """
        data = request.POST
        AuditLog.objects.create(
            action='ReceivedPayfortDirectFeedback',
            gateway=self.payment_processor.SLUG,
            details=data
        )
        if data.get('status') == SUCCESS_STATUS:
            verify_response_format(data)
            reference = data.get('merchant_reference')
            site_id_str, cart_id_str = reference.split('-', 1)
            cart = self.payment_processor.get_cart(cart_id_str)
            if cart.status != Cart.Status.PROCESSING:
                raise PayFortException(
                    f'Cart with id: {cart.id} is not in {Cart.Status.PROCESSING} state. State found: {cart.status}'
                )
            site = self.payment_processor.get_site(site_id_str)

            AuditLog.objects.create(
                user=cart.user,
                action='SuccessPayfortResponse',
                gateway=self.payment_processor.SLUG,
                details=f'Success response is receieved for cart: {cart.id} and site: {site.id}.'
            )

            with transaction.atomic():
                logger.info('Starting transaction record creation for PayFort callback.')
                self.payment_processor.handle_payment(
                    cart=cart,
                    user=request.user if request.user.is_authenticated else None,
                    transaction_status=data.get('response_message', 'unknown'),
                    transaction_id=data.get('fort_id'),
                    method=data.get('payment_option', 'N/A'),
                    amount=data.get('amount', '0'),
                    currency=data.get('currency', 'N/A'),
                    reason=data.get('acquirer_response_message', 'N/A'),
                    response=data
                )
                try:
                    self.payment_processor.fulfill_cart(cart)
                    return render(request, 'zeitlabs_payments/payment_successful.html', {'cart': cart, 'site': site})
                except CartFulfillmentError:
                    return render(request, 'zeitlabs_payments/payment_error.html')
        else:
            logger.warning(f'PayFort payment is not successful. Status: {data.get("status")}, Data: {data}')
            return render(request, 'zeitlabs_payments/payment_pending.html')
