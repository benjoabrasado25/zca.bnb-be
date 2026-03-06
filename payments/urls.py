"""Payment URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, XenditWebhookView

app_name = 'payments'

router = DefaultRouter()
router.register(r'', PaymentViewSet, basename='payment')

urlpatterns = [
    path('webhook/xendit/', XenditWebhookView.as_view(), name='xendit-webhook'),
    path('', include(router.urls)),
]
