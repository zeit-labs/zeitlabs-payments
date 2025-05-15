from rest_framework import serializers
from .models import Product, ProductSKU, CourseSKU, Cart, CartItem
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'title', 'slug', 'description', 'type', 'price']


class ProductSKUSerializer(serializers.ModelSerializer):
    product = ProductSerializer()

    class Meta:
        model = ProductSKU
        fields = ['id', 'sku', 'product']


class CourseSKUSerializer(ProductSKUSerializer):
    course_id = serializers.SerializerMethodField()

    class Meta(ProductSKUSerializer.Meta):
        model = CourseSKU
        fields = ProductSKUSerializer.Meta.fields + ['course']

    def get_course_id(self, obj):
        return str(obj.course.id)


class CartItemSerializer(serializers.ModelSerializer):
    product_sku = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ['id', 'product_sku', 'quantity', 'total_price']

    def get_product_sku(self, obj):
        # Use specific serializer based on type
        if isinstance(obj.product_sku, CourseSKU):
            return CourseSKUSerializer(obj.product_sku).data
        return ProductSKUSerializer(obj.product_sku).data

    def get_total_price(self, obj):
        return obj.total_price()


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'state', 'created_at', 'items', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price()
