"""Booking URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, BlockedDateViewSet, CheckoutView

app_name = 'bookings'

router = DefaultRouter()
router.register(r'blocked-dates', BlockedDateViewSet, basename='blocked-date')
router.register(r'', BookingViewSet, basename='booking')

urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('', include(router.urls)),
]
