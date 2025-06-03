"""Django admin view for the models."""
from django.contrib import admin

from .models import Cart, CartItem, CatalogueItem, Transaction, WebhookEvent


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Cart model.
    """

    list_display = ('id', 'user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'id')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CartItem model.
    """

    list_display = ('id', 'cart', 'catalogue_item', 'final_price', 'discount_amount')
    list_filter = ('cart__status',)
    search_fields = ('cart__id', 'catalogue_item__sku')


@admin.register(CatalogueItem)
class CatalogueItemAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CatalogueItem model.
    """

    list_display = ('id', 'sku', 'type', 'price', 'currency')
    list_filter = ('type',)
    search_fields = ('sku',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Transaction model.
    """

    list_display = (
        'id',
        'cart',
        'type',
        'status',
        'gateway',
        'gateway_transaction_id',
        'method',
        'amount',
        'currency',
        'initiator_user',
        'created_at',
    )
    list_filter = ('type', 'status', 'gateway', 'method', 'currency', 'created_at')
    search_fields = ('gateway_transaction_id', 'cart__id', 'initiator_user__username', 'initiator_user__email')
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('cart', 'initiator_user')


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    """
    Admin configuration for the WebhookEvent model.
    """

    list_display = (
        'id',
        'gateway',
        'event_type',
        'related_transaction',
        'created_at',
        'handled',
    )
    list_filter = ('gateway', 'event_type', 'handled', 'created_at')
    search_fields = ('id', 'gateway', 'event_type', 'related_transaction__gateway_transaction_id')
    readonly_fields = ('id', 'created_at')
    raw_id_fields = ('related_transaction',)
