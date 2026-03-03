"""Booking URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, BlockedDateViewSet

app_name = 'bookings'

router = DefaultRouter()
router.register(r'', BookingViewSet, basename='booking')
router.register(r'blocked-dates', BlockedDateViewSet, basename='blocked-date')

urlpatterns = [
    path('', include(router.urls)),
]
