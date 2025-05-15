from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

from futurex_ecommerce.constants import (
    CART_STATE_CHOICES,
    CART_STATE_OPEN,
    PRODUCT_TYPE_CHOICES,
    PRODUCT_TYPE_COURSE,
)
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


User = get_user_model()


class Product(models.Model):
    """Product model"""
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default=PRODUCT_TYPE_COURSE)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

    def __str__(self):
        return self.title


class ProductSKU(models.Model):
    product = models.ForeignKey(Product, related_name='skus', on_delete=models.CASCADE)
    sku = models.CharField(max_length=255)


class CourseSKU(ProductSKU):
    course = models.ForeignKey(CourseOverview, on_delete=models.CASCADE)
    # course_mode ?


class Cart(models.Model):
    """Cart model"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    state = models.CharField(max_length=20, choices=CART_STATE_CHOICES, default=CART_STATE_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart #{self.id} for {self.user}"

    def total_price(self):
        return sum(item.total_price() for item in self.items.all())


class CartItem(models.Model):
    """Cart Item model"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_sku = models.ForeignKey(ProductSKU, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product_sku')

    def total_price(self):
        return self.product_sku.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} × {self.product_sku.product.title}"
