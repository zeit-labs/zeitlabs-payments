from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from .models import Cart, CartItem, ProductSKU
from .serializers import CartSerializer

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name='dispatch')
class CartView(APIView):
    """
    ViewSet for managing user's shopping cart.
    Supports retrieving current cart and adding a SKU to the cart.
    """
    permission_classes = [IsAuthenticated]

    def get_cart(self, user):
        """
        Retrieve or create an open cart for the given user.

        :param user: User instance
        :param_type user: django.contrib.auth.get_user_model()

        :return: Cart instance
        :rtype: Cart
        """
        cart, _ = Cart.objects.get_or_create(user=user, state='open')
        return cart
    
    def get(self, user):
        """
        Retrieve or create an open cart for the given user.

        :param user: User instance
        :param_type user: django.contrib.auth.get_user_model()

        :return: Cart instance
        :rtype: Cart
        """
        cart = self.get_cart(self.request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Add or update a product in the user's cart based on SKU.

        Expected payload:
        {
            "sku": "courseSS101",
        }

        :param request: HTTP request with SKU and quantity
        :param_type request: rest_framework.request.Request

        :return: Serialized cart data with updated items
        :rtype: rest_framework.response.Response
        """
        sku_code = request.data.get('sku')
        quantity = int(request.data.get('quantity', 1))

        if not sku_code:
            return Response(
                {"error": "SKU is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        product_sku = get_object_or_404(ProductSKU, sku=sku_code)

        cart = self.get_cart(request.user)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product_sku=product_sku
        )

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
