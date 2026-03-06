"""Booking models for ZCA BnB with database-level double-booking prevention."""

import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError

from listings.models import Listing


class Booking(models.Model):
    """
    Booking model with database-level protection against double bookings.

    Uses PostgreSQL exclusion constraint to prevent overlapping date ranges.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        AIRBNB_ICAL = 'airbnb_ical', 'Airbnb iCal'
        BOOKING_COM_ICAL = 'booking_com_ical', 'Booking.com iCal'
        OTHER_ICAL = 'other_ical', 'Other iCal'

    id = models.BigAutoField(primary_key=True)
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    guest = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        null=True,
        blank=True,
    )
    guest_id_document = models.ForeignKey(
        'users.GuestID',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings',
        help_text='Guest ID document used for verification',
    )

    # Dates
    check_in = models.DateField()
    check_out = models.DateField()

    # Pricing
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='PHP')

    # Guest details
    num_guests = models.PositiveIntegerField(default=1)
    guest_name = models.CharField(max_length=255, blank=True)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=20, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )

    # iCal sync
    external_uid = models.CharField(
        max_length=255,
        blank=True,
        help_text='UID from external iCal source for deduplication',
    )

    # Notes
    special_requests = models.TextField(blank=True)
    host_notes = models.TextField(blank=True)
    message_to_host = models.TextField(
        blank=True,
        help_text='Initial message from guest to host',
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['listing', 'check_in', 'check_out']),
            models.Index(fields=['listing', 'status']),
            models.Index(fields=['guest', 'status']),
            models.Index(fields=['external_uid']),
        ]

    def __str__(self):
        return f"Booking {self.id}: {self.listing.title} ({self.check_in} - {self.check_out})"

    def clean(self):
        """Validate booking data."""
        if self.check_out <= self.check_in:
            raise ValidationError({
                'check_out': 'Check-out date must be after check-in date.'
            })

        if self.num_guests > self.listing.max_guests:
            raise ValidationError({
                'num_guests': f'Maximum guests allowed is {self.listing.max_guests}.'
            })

        nights = (self.check_out - self.check_in).days
        if nights < self.listing.minimum_nights:
            raise ValidationError({
                'check_out': f'Minimum stay is {self.listing.minimum_nights} nights.'
            })

        if nights > self.listing.maximum_nights:
            raise ValidationError({
                'check_out': f'Maximum stay is {self.listing.maximum_nights} nights.'
            })

    @property
    def nights(self):
        """Calculate number of nights."""
        return (self.check_out - self.check_in).days

    def calculate_total(self):
        """Calculate total price for the booking."""
        nights = self.nights
        subtotal = self.price_per_night * nights
        return subtotal + self.cleaning_fee


class BlockedDate(models.Model):
    """
    Blocked dates for a listing (host-defined unavailable periods).

    Used for dates when the host doesn't want bookings but isn't a booking itself.
    """

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='blocked_dates',
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blocked_dates'
        ordering = ['start_date']

    def clean(self):
        if self.end_date < self.start_date:
            raise ValidationError({
                'end_date': 'End date must be on or after start date.'
            })

    def __str__(self):
        return f"Blocked: {self.listing.title} ({self.start_date} - {self.end_date})"
