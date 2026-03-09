"""Integration models for ZCA BnB."""

from django.db import models

from listings.models import Listing


class IcalSync(models.Model):
    """
    iCal synchronization configuration for a listing.

    Stores the Airbnb (or other platform) iCal URL for importing bookings.
    """

    class SyncStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        ERROR = 'error', 'Error'

    class Platform(models.TextChoices):
        AIRBNB = 'airbnb', 'Airbnb'
        BOOKING_COM = 'booking_com', 'Booking.com'
        VRBO = 'vrbo', 'VRBO'
        OTHER = 'other', 'Other'

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='ical_syncs',
    )
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.AIRBNB,
    )
    airbnb_import_url = models.URLField(
        max_length=1000,
        help_text='iCal URL from Airbnb or other platform',
    )
    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.ACTIVE,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    sync_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ical_syncs'
        verbose_name = 'iCal Sync'
        verbose_name_plural = 'iCal Syncs'
        unique_together = ['listing', 'airbnb_import_url']

    def __str__(self):
        return f"iCal Sync: {self.listing.title} ({self.platform})"


class IcalSyncLog(models.Model):
    """Log of iCal sync operations."""

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'
        PARTIAL = 'partial', 'Partial'

    ical_sync = models.ForeignKey(
        IcalSync,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )
    events_found = models.PositiveIntegerField(default=0)
    events_created = models.PositiveIntegerField(default=0)
    events_updated = models.PositiveIntegerField(default=0)
    events_skipped = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ical_sync_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Sync Log: {self.ical_sync.listing.title} at {self.created_at}"


class AirbnbSyncJob(models.Model):
    """Track sync jobs for importing Airbnb listings."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    run_id = models.CharField(max_length=100, unique=True)
    airbnb_urls = models.JSONField(default=list, help_text='List of Airbnb URLs to sync')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    listings_created = models.PositiveIntegerField(default=0)
    listings_updated = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'airbnb_sync_jobs'
        verbose_name = 'Airbnb Sync Job'
        verbose_name_plural = 'Airbnb Sync Jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Airbnb Sync {self.run_id} ({self.status})"


# Alias for backwards compatibility
ApifySyncJob = AirbnbSyncJob


class GooglePlacesSyncJob(models.Model):
    """Track sync jobs for importing hotels from Google Places API."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'

    job_id = models.CharField(max_length=100, unique=True)
    search_query = models.CharField(max_length=255, help_text='Search query (e.g., "hotels in Manila")')
    city_name = models.CharField(max_length=100, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    hotels_found = models.PositiveIntegerField(default=0)
    hotels_created = models.PositiveIntegerField(default=0)
    hotels_updated = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'google_places_sync_jobs'
        verbose_name = 'Google Places Sync Job'
        verbose_name_plural = 'Google Places Sync Jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Google Places Sync - {self.city_name or self.search_query} ({self.status})"
