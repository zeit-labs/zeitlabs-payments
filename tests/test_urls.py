"""URLs configuration for testing purposes."""
from django.urls import include
from django.urls import path as rpath

urlpatterns = [
    # include the urls from the dashboard app using include
    rpath('', include('zeitlabs_payments.urls'), name='zeitlabs_payments'),
]
