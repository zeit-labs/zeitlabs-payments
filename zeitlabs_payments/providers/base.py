"""Base processor."""

import logging
from typing import Any, Optional

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseEnrollment
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from zeitlabs_payments.exceptions import CartFulfillmentError, GatewayError, InavlidCartError
from zeitlabs_payments.helpers import get_currency, get_language, get_merchant_reference, get_order_description
from zeitlabs_payments.models import Cart, CatalogueItem, Transaction, WebhookEvent, AuditLog

logger = logging.getLogger(__name__)


class BaseProcessor:
    """Base class for all payment processors."""

    SLUG: str
    NAME: str
    CHECKOUT_TEXT: str
    PAYMENT_INITIALIZATION_URL: str

    def get_transaction_parameters(
        self,
        cart: Cart,
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

    def get_transaction_parameters_base(
        self,
        cart: Cart,
        request: HttpRequest
    ) -> dict:
        """
        Generate base parameters required for the transaction signature.
        """
        return {
            'language': get_language(request),
            'order_reference': get_merchant_reference(request.site.id, cart),
            'amount': int(round(cart.total * 100, 0)),
            'currency': get_currency(cart),
            'user_email': cart.user.email,
            'order_description': get_order_description(cart),
        }

    def payment_view(
        self,
        cart: Cart,
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
        return render(request, f'zeitlabs_payments/processors/{self.SLUG}.html', {
            'transaction_parameters': transaction_parameters,
        })

    def get_cart(self, cart_id: str | int) -> Cart:
        """
        Retrieve a Cart instance from a string or integer cart ID.

        :param cart_id: The cart ID, as string or integer.
        :return: Cart instance if found.
        :raises GatewayError: If the cart does not exist or the ID is invalid.
        """
        try:
            cart_id_int = int(cart_id)
        except (ValueError, TypeError) as exc:
            raise InavlidCartError(f'Invalid cart ID: {cart_id}') from exc

        try:
            return Cart.objects.get(id=cart_id_int)
        except Cart.DoesNotExist as exc:
            raise InavlidCartError(f'Cart with ID {cart_id} does not exist.') from exc

    def get_site(self, site_id: str | int) -> Site:
        """
        Retrieve a Site instance from a string or integer site ID.

        :param site_id: The site ID, as string or integer.
        :return: Site instance if found.
        :raises GatewayError: If the site does not exist or the ID is invalid.
        """
        try:
            site_id_int = int(site_id)
        except (ValueError, TypeError) as exc:
            raise GatewayError(f'Invalid site ID: {site_id}') from exc

        try:
            return Site.objects.get(id=site_id_int)
        except Site.DoesNotExist as exc:
            raise GatewayError(f'Site with ID {site_id} does not exist.') from exc

    def handle_payment(  # pylint: disable= too-many-positional-arguments
        self,
        cart: Cart,
        user: get_user_model,
        transaction_status: str,
        transaction_id: str,
        method: str,
        amount: str,
        currency: str,
        reason: str,
        response: dict = None,
    ) -> None:
        """
        Retrieve a Site instance from a string or integer site ID.

        :param site_id: The site ID, as string or integer.
        :return: Site instance if found.
        :raises GatewayError: If the site does not exist or the ID is invalid.
        """
        transaction_record = Transaction.objects.create(
            cart=cart,
            type=Transaction.TransactionType.PAYMENT,
            status=transaction_status,
            gateway=self.SLUG,
            gateway_transaction_id=transaction_id,
            method=method,
            amount=amount,
            currency=currency,
            response=response,
            reason=reason,
            initiator_user=user,
            created_at=now(),
        )
        logger.info(f'Transaction recorded successfully: {transaction_record.id}')

        WebhookEvent.objects.create(
            gateway=self.SLUG,
            event_type='direct-feedback',
            payload=response,
            related_transaction=transaction_record
        )

        cart.status = Cart.Status.PAID
        cart.save(update_fields=['status'])
        AuditLog.audit_log_cart_status_updated(
            cart.user,
            cart.id,
            Cart.Status.PROCESSING,
            Cart.Status.PAID,
        )
        logger.info(f'Cart marked as PAID: {cart.id}')

    def fulfill_cart(self, cart: Cart) -> None:
        """
        Fulfill the cart by processing each item.

        If the item is a paid course, enroll the user in the course.
        Raises CartFulfillmentError if any issue occurs during processing.

        :param cart: Cart instance containing items to process
        :raises CartFulfillmentError: If any error occurs while fulfilling the cart
        """
        for item in cart.items.all():
            logger.debug(f'Processing item {item.id} in cart.')

            if item.catalogue_item.type != CatalogueItem.ItemType.PAID_COURSE:
                logger.error(
                    f'Unsupported catalogue item type: {item.catalogue_item.type} '
                    f'for item {item.catalogue_item.id} in cart {cart.id}'
                )
                AuditLog.objects.create(
                    user=cart.user,
                    action='CartFulfillmentError',
                    gateway=self.SLUG,
                    details=(
                        f'Error during cart: {cart.id} fullfilment for item: {item.id}, catalogue_item:'
                        f' {item.catalogue_item.id} due to unsupported type: {item.catalogue_item.type}.'
                    )
                )
                raise CartFulfillmentError(f'Unsupported catalogue item type: {item.catalogue_item.type}')

            try:
                course_mode = CourseMode.objects.get(sku=item.catalogue_item.sku)
            except CourseMode.DoesNotExist as exc:
                logger.error(
                    f'CourseMode not found for SKU: {item.catalogue_item.sku} - Item ID: {item.id}'
                )
                AuditLog.objects.create(
                    user=cart.user,
                    action='CartFulfillmentError',
                    gateway=self.SLUG,
                    details=(
                        f'Error during cart: {cart.id} fullfilment for item: {item.id}, catalogue_item:'
                        f' {item.catalogue_item.id} due to invalid sku: {item.catalogue_item.sku} as'
                        f'CourseMode does not exist for given sku and catalogue item type: {item.catalogue_item.type}.'
                    )
                )
                raise CartFulfillmentError('CourseMode not found') from exc

            try:
                CourseEnrollment.enroll(
                    cart.user,
                    course_mode.course.id,
                    mode=course_mode.mode_slug,
                )
                AuditLog.objects.create(
                    user=cart.user,
                    action='UserEnrolled',
                    gateway=self.SLUG,
                    details=(
                        f'User enrolled to the course: {course_mode.course.id} with mode: {course_mode.mode_slug} '
                        f'during cart: {cart.id} fullfilment for catalogue_item: {item.catalogue_item.id}.'
                    )
                )
                logger.info(
                    f'User {cart.user.id} enrolled in course {course_mode.course.id} '
                    f'with mode {course_mode.mode_slug}'
                )
            except Exception as exc:
                logger.exception(
                    f'Unexpected error while enrolling user {cart.user.id} in course: '
                    f'{course_mode.course.id}. Item ID: {item.id}'
                )
                AuditLog.objects.create(
                    user=cart.user,
                    action='UserEnrolledError',
                    gateway=self.SLUG,
                    details=(
                        f'Unable to complete user enrollment to course: {course_mode.course.id} with mode: '
                        f'{course_mode.mode_slug} during cart: {cart.id} fullfilment for'
                        f'catalogue_item: {item.catalogue_item.id}.'
                    )
                )
                raise CartFulfillmentError('Unexpected enrollment error') from exc
