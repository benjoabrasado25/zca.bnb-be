"""Integration views for ZCA BnB."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing
from .models import IcalSync, IcalSyncLog
from .serializers import (
    IcalSyncSerializer,
    IcalSyncCreateSerializer,
    IcalSyncLogSerializer,
)
from .ical_service import IcalExportService, IcalImportService


class IcalExportView(APIView):
    """
    View for exporting listing calendar as iCal.

    GET /api/listings/{id}/calendar.ics
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request, listing_id, token):
        """
        Export listing calendar as iCal.

        Requires the listing's ical_export_token for authentication.
        """
        # Validate token and get listing
        listing = get_object_or_404(
            Listing,
            id=listing_id,
            ical_export_token=token,
            status=Listing.Status.ACTIVE,
        )

        # Generate iCal content
        ical_content = IcalExportService.generate_calendar(listing)

        # Return as .ics file
        response = HttpResponse(
            ical_content,
            content_type='text/calendar; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="{listing.id}-calendar.ics"'

        return response


class IcalSyncViewSet(viewsets.ModelViewSet):
    """ViewSet for managing iCal sync configurations."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return IcalSync.objects.filter(
            listing__host=self.request.user
        ).select_related('listing')

    def get_serializer_class(self):
        if self.action == 'create':
            return IcalSyncCreateSerializer
        return IcalSyncSerializer

    def perform_create(self, serializer):
        # Verify user owns the listing
        listing = serializer.validated_data['listing']
        if listing.host != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only add iCal syncs for your own listings')
        serializer.save()

    @action(detail=True, methods=['post'])
    def sync_now(self, request, pk=None):
        """Manually trigger a sync for this iCal configuration."""
        ical_sync = self.get_object()

        created, updated, skipped, error = IcalImportService.sync_ical(ical_sync)

        # Create log entry
        log_status = IcalSyncLog.Status.SUCCESS if not error else IcalSyncLog.Status.FAILED
        IcalSyncLog.objects.create(
            ical_sync=ical_sync,
            status=log_status,
            events_found=created + updated + skipped,
            events_created=created,
            events_updated=updated,
            events_skipped=skipped,
            error_message=error,
        )

        # Update sync record
        from django.utils import timezone
        ical_sync.last_synced_at = timezone.now()
        ical_sync.sync_count += 1
        ical_sync.last_error = error
        ical_sync.status = IcalSync.SyncStatus.ERROR if error else IcalSync.SyncStatus.ACTIVE
        ical_sync.save()

        if error:
            return Response({
                'status': 'error',
                'message': error,
                'events_created': created,
                'events_updated': updated,
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status': 'success',
            'events_created': created,
            'events_updated': updated,
            'events_skipped': skipped,
        })

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get sync logs for this iCal configuration."""
        ical_sync = self.get_object()
        logs = ical_sync.logs.all()[:20]
        serializer = IcalSyncLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause syncing for this iCal configuration."""
        ical_sync = self.get_object()
        ical_sync.status = IcalSync.SyncStatus.PAUSED
        ical_sync.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'paused'})

    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume syncing for this iCal configuration."""
        ical_sync = self.get_object()
        ical_sync.status = IcalSync.SyncStatus.ACTIVE
        ical_sync.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'active'})


class IcalExportUrlView(APIView):
    """View for getting the iCal export URL for a listing."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, listing_id):
        """Get the iCal export URL for a listing."""
        listing = get_object_or_404(
            Listing,
            id=listing_id,
            host=request.user,
        )

        # Build the export URL
        export_url = request.build_absolute_uri(
            f'/api/listings/{listing.id}/calendar/{listing.ical_export_token}.ics'
        )

        return Response({
            'listing_id': listing.id,
            'export_url': export_url,
            'instructions': (
                'Add this URL to Airbnb or other platforms to sync your availability. '
                'This URL is unique to your listing and should be kept private.'
            ),
        })

    def post(self, request, listing_id):
        """Regenerate the iCal export token for a listing."""
        listing = get_object_or_404(
            Listing,
            id=listing_id,
            host=request.user,
        )

        listing.regenerate_ical_token()

        export_url = request.build_absolute_uri(
            f'/api/listings/{listing.id}/calendar/{listing.ical_export_token}.ics'
        )

        return Response({
            'message': 'Export URL regenerated. Update this URL in any external platforms.',
            'export_url': export_url,
        })
