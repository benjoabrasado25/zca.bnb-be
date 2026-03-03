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
