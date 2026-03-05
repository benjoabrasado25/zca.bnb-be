"""Listing URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import ListingViewSet, ListingImageViewSet, AmenityViewSet, CityViewSet

app_name = 'listings'

# Create router for listings (with empty prefix since mounted at /api/listings/)
router = DefaultRouter()
router.register(r'', ListingViewSet, basename='listing')

# Separate routers for amenities and cities to avoid conflicts
amenity_router = DefaultRouter()
amenity_router.register(r'', AmenityViewSet, basename='amenity')

city_router = DefaultRouter()
city_router.register(r'', CityViewSet, basename='city')

# Nested router for listing images
listings_router = routers.NestedDefaultRouter(router, r'', lookup='listing')
listings_router.register(r'images', ListingImageViewSet, basename='listing-images')

urlpatterns = [
    # Amenities and cities must come BEFORE the main listing routes
    path('amenities/', include(amenity_router.urls)),
    path('cities/', include(city_router.urls)),
    # Main listing routes
    path('', include(router.urls)),
    path('', include(listings_router.urls)),
]
