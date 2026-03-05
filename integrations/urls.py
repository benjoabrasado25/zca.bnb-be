"""Integration URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    IcalSyncViewSet,
    IcalExportView,
    IcalExportUrlView,
    AirbnbSyncView,
    AirbnbSyncJobsView,
)

app_name = 'integrations'

router = DefaultRouter()
router.register(r'ical-syncs', IcalSyncViewSet, basename='ical-sync')

urlpatterns = [
    path('', include(router.urls)),
    path('listings/<int:listing_id>/export-url/', IcalExportUrlView.as_view(), name='ical-export-url'),
    # Airbnb sync endpoints for hosts
    path('airbnb-sync/', AirbnbSyncView.as_view(), name='airbnb-sync'),
    path('airbnb-sync/jobs/', AirbnbSyncJobsView.as_view(), name='airbnb-sync-jobs'),
]

# Add the calendar export URL to listings URLs
# This will be included in the main urls.py
ical_export_patterns = [
    path(
        'listings/<int:listing_id>/calendar/<uuid:token>.ics',
        IcalExportView.as_view(),
        name='ical-export',
    ),
]
