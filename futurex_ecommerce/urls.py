from django.urls import re_path, include
from rest_framework.routers import DefaultRouter
from futurex_ecommerce import views

router = DefaultRouter()

urlpatterns = [
    re_path(r'^api/fx/cart/v1/add/$', views.CartView.as_view(), name='cart_add'),
]
