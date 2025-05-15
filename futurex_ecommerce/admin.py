"""Django Admin Models"""
from django.contrib import admin
from .models import Product, ProductSKU, CourseSKU, Cart, CartItem


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin interface for Product model.

    :param model: Product model.
    :type model: Model
    """

    list_display = ('title', 'type', 'price', 'is_active', 'created_at')
    search_fields = ('title', 'slug')
    list_filter = ('type', 'is_active')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(CourseSKU)
class CourseSKUAdmin(admin.ModelAdmin):
    """
    Admin interface for CourseSKU model.

    :param model: CourseSKU model.
    :type model: Model
    """

    list_display = ('sku', 'product', 'course')
    search_fields = ('sku',)
    list_filter = ('product', 'course')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin interface for Cart model.

    :param model: Cart model.
    :type model: Model
    """

    list_display = ('id', 'user', 'state', 'created_at')
    search_fields = ('user__email',)
    list_filter = ('state',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Admin interface for CartItem model.

    :param model: CartItem model.
    :type model: Model
    """

    list_display = ('cart', 'product_sku', 'quantity')
    search_fields = ('cart__user__email', 'product_sku__product__title')
