"""Payfort Views"""

import logging
from typing import Any

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from django.contrib.sites.models import Site
from django.db import transaction
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from zeitlabs_payments.models import Cart, CatalogueItem, Transaction, WebhookEvent
from zeitlabs_payments.providers.payfort.exceptions import PayFortException
from zeitlabs_payments.providers.payfort.helpers import SUCCESS_STATUS, verify_response_format

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PayfortFeedbackView(View):
    """
    Callback endpoint for PayFort to notify about payment status.
    """

    def post(self, request: Any) -> None:
        """
        Handle the callback POST request from PayFort.

        :param request: DRF request object
        :return: Rendered invoice page or HTTP response

        TODO: use audit log for everything including failed transaction. Webhook event is only for success transactions.
        """
        data = request.POST
        webhook_event = WebhookEvent.objects.create(
            gateway='payfort',
            event_type='direct-feedback',
            payload=data
        )

        verify_response_format(data)
        reference = data.get('merchant_reference')
        site_id_str, cart_id_str = reference.split('-', 1)

        try:
            cart = Cart.objects.get(id=int(cart_id_str))
        except Cart.DoesNotExist as exc:
            raise PayFortException(f'Cart with id: {cart_id_str} does not exist.') from exc

        if cart.status != Cart.Status.PROCESSING:
            raise PayFortException(
                f'Cart with id: {cart.id} is not in {Cart.Status.PROCESSING} state. State found: {cart.status}'
            )

        try:
            site = Site.objects.get(id=int(site_id_str))
        except Site.DoesNotExist as exc:
            raise PayFortException(f'Site with id: {site_id_str} does not exist.') from exc

        # processor = PayFort()
        # transaction_parameters = processor.get_transaction_parameters_base(cart, request)
        # transaction_parameters['signature'] = data.get('signature')
        # verify_signature(
        #     processor.request_sha_phrase,
        #     processor.sha_method,
        #     transaction_parameters,
        # )

        if data.get('status') == SUCCESS_STATUS:
            with transaction.atomic():
                logger.info('Starting transaction record creation for PayFort callback.')

                transaction_record = Transaction.objects.create(
                    cart=cart,
                    type=Transaction.TransactionType.PAYMENT,
                    status=data.get('response_message', 'unknown'),
                    gateway='payfort',
                    gateway_transaction_id=data.get('fort_id'),
                    method=data.get('payment_option', 'unknown'),
                    amount=data.get('amount', '0'),
                    currency=data.get('currency', 'SAR'),
                    response=data,
                    reason=data.get('acquirer_response_message', 'N/A'),
                    initiator_user=request.user if request.user.is_authenticated else None,
                    created_at=now(),
                )
                logger.info(f'Transaction recorded successfully: {transaction_record.id}')

                cart.status = Cart.Status.PAID
                cart.save(update_fields=['status'])
                logger.info(f'Cart marked as PAID: {cart.id}')

                webhook_event.related_transaction = transaction_record
                webhook_event.save()

                for item in cart.items.all():
                    logger.debug(f'Processing item {item.id} in cart.')
                    if item.catalogue_item.type == CatalogueItem.ItemType.PAID_COURSE:
                        try:
                            course_mode = CourseMode.objects.get(sku=item.catalogue_item.sku)
                            CourseEnrollment.enroll(
                                cart.user,
                                course_mode.course.id,
                                mode=course_mode.mode_slug,
                            )
                            logger.info(
                                f'User {cart.user.id} enrolled in course {course_mode.course.id} '
                                f'with mode {course_mode.mode_slug}'
                            )
                        except CourseMode.DoesNotExist:
                            logger.error(
                                f'CourseMode not found for SKU: {item.catalogue_item.sku} - Item ID: {item.id}'
                            )
                            return render(request, 'zeitlabs_payments/payment_error.html')
                        except Exception:  # pylint: disable=broad-exception-caught
                            logger.exception(
                                f'Unexpected error while enrolling user {cart.user.id} in course: '
                                f'{course_mode.course.id}. Item ID: {item.id}'
                            )
                            return render(request, 'zeitlabs_payments/payment_error.html')
                    else:
                        logger.exception(
                            f'Cart with id: {cart.id} contains unsupported catalogue item: {item.catalogue_item.id} '
                            f'of type: {item.catalogue_item.type}'
                        )
                        return render(request, 'zeitlabs_payments/payment_error.html')
                return render(request, 'zeitlabs_payments/payment_successful.html', {'cart': cart, 'site': site})
        else:
            logger.warning(f'PayFort payment failed. Status: {data.get("status")}, Data: {data}')
            return render(request, 'zeitlabs_payments/payment_unsuccessful.html')
