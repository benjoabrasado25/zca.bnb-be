"""Listing models for ZCA BnB."""

import uuid

from django.conf import settings
from django.db import models


class Listing(models.Model):
    """
    Listing model representing a property for rent.
    """

    class PropertyType(models.TextChoices):
        ENTIRE_PLACE = 'entire_place', 'Entire Place'
        PRIVATE_ROOM = 'private_room', 'Private Room'
        SHARED_ROOM = 'shared_room', 'Shared Room'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    id = models.BigAutoField(primary_key=True)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='listings',
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.ENTIRE_PLACE,
    )

    # Location
    address = models.CharField(max_length=500)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='Philippines')
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Pricing
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    cleaning_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    currency = models.CharField(max_length=3, default='PHP')

    # Capacity
    max_guests = models.PositiveIntegerField(default=1)
    bedrooms = models.PositiveIntegerField(default=1)
    beds = models.PositiveIntegerField(default=1)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1)

    # Rules
    minimum_nights = models.PositiveIntegerField(default=1)
    maximum_nights = models.PositiveIntegerField(default=365)
    check_in_time = models.TimeField(default='14:00')
    check_out_time = models.TimeField(default='11:00')

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_instant_bookable = models.BooleanField(default=False)

    # iCal Integration
    ical_export_token = models.UUIDField(default=uuid.uuid4, unique=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'listings'
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['city']),
            models.Index(fields=['status']),
            models.Index(fields=['price_per_night']),
            models.Index(fields=['host', 'status']),
        ]

    def __str__(self):
        return f"{self.title} - {self.city}"

    def regenerate_ical_token(self):
        """Regenerate the iCal export token."""
        self.ical_export_token = uuid.uuid4()
        self.save(update_fields=['ical_export_token'])


class ListingImage(models.Model):
    """Images associated with a listing."""

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='listing_images/')
    caption = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'listing_images'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Image for {self.listing.title}"


class ListingAmenity(models.Model):
    """Amenities available at a listing."""

    class AmenityCategory(models.TextChoices):
        ESSENTIALS = 'essentials', 'Essentials'
        FEATURES = 'features', 'Features'
        LOCATION = 'location', 'Location'
        SAFETY = 'safety', 'Safety'

    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)
    category = models.CharField(
        max_length=20,
        choices=AmenityCategory.choices,
        default=AmenityCategory.ESSENTIALS,
    )

    class Meta:
        db_table = 'listing_amenities'
        verbose_name_plural = 'Listing Amenities'

    def __str__(self):
        return self.name


class ListingAmenityMapping(models.Model):
    """Many-to-many relationship between listings and amenities."""

    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='amenity_mappings',
    )
    amenity = models.ForeignKey(
        ListingAmenity,
        on_delete=models.CASCADE,
        related_name='listing_mappings',
    )

    class Meta:
        db_table = 'listing_amenity_mappings'
        unique_together = ['listing', 'amenity']
