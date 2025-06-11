"""Zeitlabs payments models."""
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Transaction(models.Model):
    """Transaction model."""

    class TransactionType(models.TextChoices):
        """Transaction types."""

        PAYMENT = 'payment'
        REFUND = 'refund'

    cart = models.ForeignKey('Cart', on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TransactionType.choices)
    status = models.CharField(max_length=50)
    gateway = models.CharField(max_length=50)
    gateway_transaction_id = models.CharField(max_length=255)
    method = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10)
    response = models.JSONField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    initiator_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)


class WebhookEvent(models.Model):
    """WebhookEvent model."""

    gateway = models.CharField(max_length=50)
    event_type = models.CharField(max_length=100)
    payload = models.JSONField()
    related_transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handled = models.BooleanField(default=False)


class AuditLog(models.Model):
    """AuditLog model."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    gateway = models.CharField(max_length=50, blank=True, null=True)
    details = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def audit_log_cart_status_updated(cls, user, old_status, new_status):
        cls.objects.create(
            user=user,
            action='CartStatusUpdated',
            details=f'Status updated for Cart with id: {id} from: {old_status} to: {new_status}.'
        )


class Cart(models.Model):
    """Cart model."""

    class Status(models.TextChoices):
        """Cart states."""

        PENDING = 'pending'
        PROCESSING = 'processing'
        PAID = 'paid'
        CANCELLED = 'cancelled'
        REFUND_REQUESTED = 'refund_requested'
        REFUNDED = 'refunded'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total(self) -> int:
        """Calculate total."""
        return sum(item.final_price for item in self.items.all())


class Coupon(models.Model):
    """Coupon model."""

    class DiscountType(models.TextChoices):
        """Discount Types."""

        FIXED = 'fixed'
        PERCENTAGE = 'percentage'

    code = models.CharField(max_length=50, primary_key=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_usage = models.PositiveIntegerField()
    usage_count = models.PositiveIntegerField(default=0)  # TODO: move to usage table
    expires_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CouponUsage(models.Model):
    """CouponUsage model."""

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    count = models.PositiveIntegerField(default=1)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class CatalogueItem(models.Model):
    """CatalogueItem model."""

    class ItemType(models.TextChoices):
        """Catalogue Item Types."""

        PAID_COURSE = 'paid_course'
        # TODO add other types here like 'section_of_course', 'fremium_course', etc.

    sku = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ItemType.choices)
    item_ref_id = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CartItem(models.Model):
    """CartItem model."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    catalogue_item = models.ForeignKey(CatalogueItem, on_delete=models.PROTECT)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2)


class Invoice(models.Model):
    """Invoice model."""

    class Status(models.TextChoices):
        """Invoice statuses."""

        DRAFT = 'draft'
        PAID = 'paid'
        CANCELLED = 'cancelled'

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='invoices')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)


class InvoiceItem(models.Model):
    """InvoiceItem model."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    cart_item = models.ForeignKey(CartItem, on_delete=models.SET_NULL, null=True)
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)


class CreditMemo(models.Model):
    """CreditMemo model."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='credit_memos')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    gateway_refund_transaction_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
