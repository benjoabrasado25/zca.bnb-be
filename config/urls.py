"""
URL configuration for ZCA BnB project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.db import connection
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from integrations.urls import ical_export_patterns


def health_check(request):
    """Health check endpoint for Railway with database connectivity test."""
    try:
        # Test database connectivity
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ok', 'database': 'connected'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'database': str(e)}, status=503)


urlpatterns = [
    # Health check (no auth required)
    path('health/', health_check, name='health-check'),

    path('admin/', admin.site.urls),

    # JWT Authentication
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    # OAuth / Social Authentication
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/auth/google/', include('users.oauth_urls')),
    path('accounts/', include('allauth.urls')),

    # API endpoints
    path('api/users/', include('users.urls')),
    path('api/listings/', include('listings.urls')),
    path('api/bookings/', include('bookings.urls')),
    path('api/integrations/', include('integrations.urls')),

    # iCal export (public endpoint for Airbnb to fetch)
    path('api/', include(ical_export_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
