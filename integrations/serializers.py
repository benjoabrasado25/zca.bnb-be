"""Integration serializers for ZCA BnB."""

from rest_framework import serializers

from .models import IcalSync, IcalSyncLog


class IcalSyncSerializer(serializers.ModelSerializer):
    """Serializer for iCal sync configuration."""

    listing_title = serializers.CharField(source='listing.title', read_only=True)

    class Meta:
        model = IcalSync
        fields = [
            'id',
            'listing',
            'listing_title',
            'platform',
            'airbnb_import_url',
            'status',
            'last_synced_at',
            'last_error',
            'sync_count',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'last_synced_at', 'last_error', 'sync_count', 'created_at']


class IcalSyncCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating iCal sync configuration."""

    class Meta:
        model = IcalSync
        fields = ['listing', 'platform', 'airbnb_import_url']

    def validate_airbnb_import_url(self, value):
        """Validate the iCal URL."""
        if not value.startswith('http'):
            raise serializers.ValidationError('Invalid URL format')

        # Basic validation for common iCal URLs
        valid_patterns = [
            'airbnb.com',
            'booking.com',
            'vrbo.com',
            '.ics',
            'ical',
            'calendar',
        ]

        if not any(pattern in value.lower() for pattern in valid_patterns):
            raise serializers.ValidationError(
                'URL does not appear to be a valid iCal feed URL'
            )

        return value


class IcalSyncLogSerializer(serializers.ModelSerializer):
    """Serializer for iCal sync logs."""

    class Meta:
        model = IcalSyncLog
        fields = [
            'id',
            'status',
            'events_found',
            'events_created',
            'events_updated',
            'events_skipped',
            'error_message',
            'created_at',
        ]
