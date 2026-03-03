"""Listing URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import ListingViewSet, ListingImageViewSet, AmenityViewSet

app_name = 'listings'

router = DefaultRouter()
router.register(r'', ListingViewSet, basename='listing')
router.register(r'amenities', AmenityViewSet, basename='amenity')

# Nested router for listing images
listings_router = routers.NestedDefaultRouter(router, r'', lookup='listing')
listings_router.register(r'images', ListingImageViewSet, basename='listing-images')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(listings_router.urls)),
]
