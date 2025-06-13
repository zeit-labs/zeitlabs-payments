"""Zeilabs payments views."""
import logging
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from zeitlabs_payments import models
from zeitlabs_payments.providers.registry import PROCESSORS, get_processor
from zeitlabs_payments.serializers import CartSerializer
from zeitlabs_payments.exceptions import InavlidCartError

logger = logging.getLogger(__name__)


class CheckoutView(LoginRequiredMixin, TemplateView):
    """
    View responsible for rendering the checkout page.

    This page is only accessible by authenticated users and provides a last pending cart
    along with available payment methods derived from registered processors.
    """

    template_name = 'zeitlabs_payments/checkout.html'

    def get_context_data(self, **kwargs: Any) -> dict:
        """
        Build and return the context data for the checkout page.

        :param kwargs: Additional context parameters
        :return: Context dictionary including cart and payment methods
        """
        context = super().get_context_data(**kwargs)
        cart = None
        methods = []
        cart = (
            models.Cart.objects.filter(user=self.request.user, status='pending')
            .order_by('-created_at')
            .first()
        )

        if cart:
            methods = [
                processor.get_payment_method_metadata(cart)
                for processor in PROCESSORS.values()
            ]
            cart = CartSerializer(cart, context={'request': self.request}).data

        context.update(
            {
                'cart': cart,
                'methods': methods,
            }
        )
        return context


class InitiatePaymentView(LoginRequiredMixin, View):
    """
    View that initiates the payment process for a given provider.

    Only accessible by authenticated users.
    """

    def get(self, request: Any, provider: str, cart_id: str) -> Any:
        """
        Initiate the payment by calling the appropriate processor.

        :param request: Django request object
        :param provider: The payment provider slug
        :param cart_id: UUID of the cart
        :return: Rendered payment page or error response
        """
        try:
            processor = get_processor(provider)
            logger.debug(f'Processor found for provider: {provider}')
        except ValueError as exc:
            logger.error(f'Invalid payment provider: {provider} - {exc}')
            return HttpResponseBadRequest(f'Error: {str(exc)}')

        try:
            cart = processor.get_cart(cart_id)
        except InavlidCartError as exc:
            logger.error(f'Cart not found with id: {cart_id} - {exc}')
            return HttpResponseBadRequest(f'Error: {str(exc)}')

        if request.user != cart.user:
            logger.warning(f'User {request.user} attempted to access cart {cart.id} belonging to {cart.user}')
            return HttpResponseBadRequest(
                f'Error: User {request.user} attempted to access cart belonging to {cart.user}.'
            )

        payment_view = processor.payment_view(
            cart=cart,
            request=request,
            use_client_side_checkout=False,
        )

        cart.status = models.Cart.Status.PROCESSING
        cart.save(update_fields=['status'])
        models.AuditLog.audit_log_cart_status_updated(
            cart.user,
            cart.id,
            models.Cart.Status.PENDING,
            models.Cart.Status.PROCESSING,
        )
        logger.info(f'Cart {cart.id} status updated to PROCESSING')

        models.AuditLog.objects.create(
            user=cart.user,
            action='RedirectedToPaymentGatweway',
            gateway=processor.SLUG,
            details=f'Redirecting to {processor.SLUG} payment page for cart: {cart.id}.'
        )
        return payment_view


@method_decorator(csrf_exempt, name='dispatch')
class CartView(APIView):
    """
    ViewSet for managing user's shopping cart.

    Supports retrieving current cart and adding a SKU to the cart.
    """

    permission_classes = [IsAuthenticated]

    def create_cart(self, user: get_user_model, catalog_item: models.CatalogueItem) -> models.Cart:
        """
        Create an open cart for the given user.

        :param user: User instance
        :param catalog_item: CatalogueItem instance to add to cart
        :return: Cart instance
        """
        pending_carts = models.Cart.objects.filter(user=user, status=models.Cart.Status.PENDING)
        cart_ids = list(pending_carts.values_list('id', flat=True))
        updated_count = pending_carts.update(status=models.Cart.Status.CANCELLED)
        logger.debug(f'Cancelled {updated_count} previous pending carts for user {user} with IDs: {cart_ids}')
        for id in cart_ids:
            models.AuditLog.audit_log_cart_status_updated(
                user,
                id,
                models.Cart.Status.PENDING,
                models.Cart.Status.CANCELLED,
            )

        cart = models.Cart.objects.create(user=user, status=models.Cart.Status.PENDING)
        logger.info(f'Created new pending cart {cart.id} for user {user}')
        models.AuditLog.objects.create(
            user=user,
            action='CreatedCart',
            details=f'Cart with id: {cart.id} is created.'
        )
        models.CartItem.objects.create(
            cart=cart,
            catalogue_item=catalog_item,
            original_price=catalog_item.price,
            final_price=catalog_item.price,
        )
        logger.info(f'Added catalogue item {catalog_item.sku} to cart {cart.id}')
        models.AuditLog.objects.create(
            user=user,
            action='AddedItemToCart',
            details=f'Added catalogue item {catalog_item.sku} to the cart {cart.id}'
        )
        return cart

    def get(self, request: Any) -> Response:
        """
        Retrieve last cart with pending state.

        :param request: HTTP request
        :return: Serialized cart data with HTTP 200 status
        """
        last_pending_cart = models.Cart.objects.filter(
            user=request.user, status=models.Cart.Status.PENDING
        ).order_by('-created_at').first()

        serializer = CartSerializer(last_pending_cart, context={'request': request})
        logger.debug(f'Retrieved last pending cart for user {request.user}: {last_pending_cart}')
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Any) -> Response:
        """
        Create a new cart and add the requested SKU item.

        Expected payload:
        {
            "sku": "courseSS101",
        }

        :param request: HTTP request with SKU in data
        :return: Serialized cart data with HTTP 201 status or error response
        """
        sku_code = request.data.get('sku')

        if not sku_code:
            logger.warning('POST to CartView missing SKU in request data')
            return Response(
                {'error': 'SKU is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            catalog_item = models.CatalogueItem.objects.get(sku=sku_code)
            logger.debug(f'Catalog item found for SKU {sku_code}')
        except models.CatalogueItem.DoesNotExist:
            return Response(
                {'error': 'Invalid SKU, iunable to find catalogue item.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        models.AuditLog.objects.create(
            user=request.user,
            action='InitiatedAddToCart',
            details='User added product with sku: {sku_code} to the cart.'
        )
        cart = self.create_cart(request.user, catalog_item)
        serializer = CartSerializer(cart, context={'request': request})
        logger.info(f'Cart created for user {request.user} with SKU {sku_code}')
        return Response(serializer.data, status=status.HTTP_201_CREATED)
