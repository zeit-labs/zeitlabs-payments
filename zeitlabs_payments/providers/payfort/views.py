import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import transaction
from django.shortcuts import render
from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from zeitlabs_payments.models import Cart, CatalogueItem, Transaction, WebhookEvent
from zeitlabs_payments.providers.payfort.exceptions import PayFortException
from zeitlabs_payments.providers.payfort.helpers import (
    SUCCESS_STATUS,
    verify_response_format,
)
from zeitlabs_payments.providers.payfort.processor import PayFort


logger = logging.getLogger(__name__)


class PayfortCallbackView(APIView):
    """
    Callback endpoint for PayFort to notify about payment status.
    """

    def post(self, request):
        """
        Handle the callback POST request from PayFort.

        :param request: DRF request object
        :return: Rendered invoice page or HTTP response
        """
        data = request.data
        WebhookEvent.objects.create(
            gateway='payfort',
            event_type=data.get('command', 'unknown'),
            payload=data
        )

        verify_response_format(data)

        reference = data.get('merchant_reference')
        if not reference or '-' not in reference:
            raise PayFortException('Invalid or missing merchant_reference.')

        try:
            site_id_str, cart_id_str = reference.split('-', 1)
            site_id = int(site_id_str)
        except ValueError:
            raise PayFortException("Malformed merchant_reference. Expected format: '<site_id>-<cart_id>'.")

        try:
            cart = Cart.objects.get(id=cart_id_str)
        except Cart.DoesNotExist:
            raise PayFortException('Invalid cart ID in PayFort callback.')

        try:
            site = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            raise PayFortException('Site with id from merchant_reference does not exist.')

        processor = PayFort()
        transaction_parameters = processor.get_transaction_parameters_base(cart, request)
        transaction_parameters['signature'] = data.get('signature')

        # Uncomment to enable signature verification
        # verify_signature(
        #     processor.request_sha_phrase,
        #     processor.sha_method,
        #     transaction_parameters,
        # )

        if data.get('status') == SUCCESS_STATUS:
            try:
                with transaction.atomic():
                    logger.info('Starting transaction record creation for PayFort callback.')

                    transaction_record = Transaction.objects.create(
                        cart=cart,
                        type=Transaction.Type.PAYMENT,
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
                            except Exception:
                                logger.exception(
                                    f'Unexpected error while enrolling user {cart.user.id} in course. '
                                    f'Item ID: {item.id}'
                                )

                    return render(request, 'zeitlabs_payments/payment_successful.html', {'cart': cart, 'site': site})

            except Exception:
                logger.exception(
                    f'Exception during PayFort payment processing for cart {cart.id}. Data: {data}'
                )
                return render(request, "zeitlabs_payments/payment_error.html")

        else:
            logger.warning(f'PayFort payment failed. Status: {data.get("status")}, Data: {data}')
            return render(request, "zeitlabs_payments/payment_unsuccessful.html")
