"""
URLs for zeitlabs_payments.
"""
from django.urls import re_path
from zeitlabs_payments import views
from zeitlabs_payments.providers.payfort import views as payfort_views

urlpatterns: list = [
    re_path(
        r'^checkout/v1/checkout/$',
        views.CheckoutView.as_view(),
        name='checkout'
    ),
    re_path(
        r'^payment/v1/initiate/(?P<provider>[\w-]+)/(?P<cart_uuid>[0-9a-f-]+)/$',
        views.InitiatePaymentView.as_view(),
        name='initiate-payment'
    ),

    # api urls
    re_path(r'^api/cart/v1/cart/$', views.CartView.as_view(), name='cart-add'),

    # provider urls
    re_path(
        r'^api/payment/v1/payfort/callback/$',
        payfort_views.PayfortCallbackView.as_view(),
        name='payfort-callback'
    ),
]
