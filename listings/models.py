"""Listing models for StaySuitePH."""

import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class City(models.Model):
    """City model for location dropdown."""

    name = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default='Philippines')
    image = models.ImageField(upload_to='city_images/', blank=True, null=True, help_text='City cover image for homepage')
    description = models.TextField(blank=True, help_text='Short description for homepage display')
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text='Show on homepage')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'cities'
        verbose_name = 'City'
        verbose_name_plural = 'Cities'
        ordering = ['order', 'name']

    def __str__(self):
        if self.province:
            return f"{self.name}, {self.province}"
        return self.name


class Listing(models.Model):
    """
    Listing model representing a property for rent.
    """

    class PropertyType(models.TextChoices):
        ENTIRE_PLACE = 'entire_place', 'Entire Place'
        PRIVATE_ROOM = 'private_room', 'Private Room'
        SHARED_ROOM = 'shared_room', 'Shared Room'

    class PropertyCategory(models.TextChoices):
        """Airbnb-style property categories."""
        HOUSE = 'house', 'House'
        APARTMENT = 'apartment', 'Apartment'
        GUESTHOUSE = 'guesthouse', 'Guesthouse'
        HOTEL = 'hotel', 'Hotel'
        VILLA = 'villa', 'Villa'
        CONDO = 'condo', 'Condo'
        TOWNHOUSE = 'townhouse', 'Townhouse'
        COTTAGE = 'cottage', 'Cottage'
        CABIN = 'cabin', 'Cabin'
        RESORT = 'resort', 'Resort'
        HOSTEL = 'hostel', 'Hostel'
        BED_AND_BREAKFAST = 'bnb', 'Bed & Breakfast'
        FARM_STAY = 'farm_stay', 'Farm Stay'
        BOAT = 'boat', 'Boat'
        CAMPER = 'camper', 'Camper/RV'
        TREEHOUSE = 'treehouse', 'Treehouse'
        TENT = 'tent', 'Tent'
        OTHER = 'other', 'Other'

    class CancellationPolicy(models.TextChoices):
        FLEXIBLE = 'flexible', 'Flexible - Full refund 1 day prior'
        MODERATE = 'moderate', 'Moderate - Full refund 5 days prior'
        STRICT = 'strict', 'Strict - 50% refund up to 1 week prior'
        SUPER_STRICT = 'super_strict', 'Super Strict - No refund'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING_REVIEW = 'pending_review', 'Pending Review'
        ACTIVE = 'active', 'Active'
        REJECTED = 'rejected', 'Rejected'
        INACTIVE = 'inactive', 'Inactive'

    id = models.BigAutoField(primary_key=True)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
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
    property_category = models.CharField(
        max_length=20,
        choices=PropertyCategory.choices,
        default=PropertyCategory.HOUSE,
    )

    # Location - City as ForeignKey for dropdown
    city = models.ForeignKey(
        City,
        on_delete=models.PROTECT,
        related_name='listings',
        null=True,
        blank=True,
    )
    city_name_old = models.CharField(max_length=100, blank=True, editable=False)  # Temporary, remove after data migration
    address = models.CharField(max_length=500)
    neighborhood = models.CharField(max_length=200, blank=True, help_text='Specific area/neighborhood')
    postal_code = models.CharField(max_length=20, blank=True)
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
    service_fee_percent = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=10.00,
        help_text='Service fee percentage charged to guests',
    )
    currency = models.CharField(max_length=3, default='PHP')
    weekly_discount = models.PositiveIntegerField(default=0, help_text='Discount % for 7+ nights')
    monthly_discount = models.PositiveIntegerField(default=0, help_text='Discount % for 28+ nights')

    # Capacity
    max_guests = models.PositiveIntegerField(default=1)
    bedrooms = models.PositiveIntegerField(default=1)
    beds = models.PositiveIntegerField(default=1)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1, default=1)

    # Property Details (Airbnb-style)
    space_description = models.TextField(blank=True, help_text='Describe the space guests will have access to')
    guest_access = models.TextField(blank=True, help_text='What areas can guests access?')
    interaction_with_guests = models.TextField(blank=True, help_text='How much will you interact with guests?')
    other_things_to_note = models.TextField(blank=True, help_text='Other important details')
    neighborhood_overview = models.TextField(blank=True, help_text='Describe the neighborhood')
    getting_around = models.TextField(blank=True, help_text='Transportation options')

    # Rules
    minimum_nights = models.PositiveIntegerField(default=1)
    maximum_nights = models.PositiveIntegerField(default=365)
    check_in_time = models.TimeField(default='14:00')
    check_out_time = models.TimeField(default='11:00')

    # House Rules (Airbnb-style)
    pets_allowed = models.BooleanField(default=False)
    smoking_allowed = models.BooleanField(default=False)
    parties_allowed = models.BooleanField(default=False)
    children_allowed = models.BooleanField(default=True)
    infants_allowed = models.BooleanField(default=True)
    additional_rules = models.TextField(blank=True, help_text='Any additional house rules')

    # Cancellation
    cancellation_policy = models.CharField(
        max_length=20,
        choices=CancellationPolicy.choices,
        default=CancellationPolicy.MODERATE,
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    is_instant_bookable = models.BooleanField(default=False)
    is_inquiry_only = models.BooleanField(default=False, help_text='Show inquiry form instead of booking')
    is_featured = models.BooleanField(default=False, help_text='Featured on homepage')

    # Airbnb Integration
    airbnb_id = models.CharField(max_length=50, blank=True, db_index=True, help_text='Airbnb listing ID')
    airbnb_url = models.URLField(max_length=500, blank=True, help_text='Full Airbnb listing URL')
    booking_url = models.URLField(max_length=500, blank=True, help_text='External booking URL')
    last_synced = models.DateTimeField(null=True, blank=True, help_text='Last Apify sync timestamp')

    # iCal Integration
    ical_export_token = models.UUIDField(default=uuid.uuid4, unique=True)
    ical_url = models.URLField(max_length=500, blank=True, help_text='iCal feed URL for availability sync')
    ical_last_synced = models.DateTimeField(null=True, blank=True)
    booked_dates = models.JSONField(default=list, blank=True, help_text='JSON array of booked date ranges from iCal')

    # Ratings & Reviews
    rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True, help_text='Overall rating 0-5')
    reviews_count = models.PositiveIntegerField(default=0)
    rating_accuracy = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_cleanliness = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_checkin = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_communication = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_location = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_value = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    reviews = models.JSONField(default=list, blank=True, help_text='JSON array of review objects')

    # Property Highlights
    highlights = models.JSONField(default=list, blank=True, help_text='JSON array of property highlights')
    square_feet = models.PositiveIntegerField(null=True, blank=True)

    # Check-in Details
    self_checkin = models.BooleanField(default=False)
    checkin_method = models.CharField(max_length=255, blank=True, help_text='e.g., Lockbox, Smart lock, Doorman')

    # Admin approval workflow
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_listings',
    )
    rejection_reason = models.TextField(blank=True)

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
            models.Index(fields=['airbnb_id']),
        ]

    def __str__(self):
        return f"{self.title} - {self.city}"

    def save(self, *args, **kwargs):
        """Generate unique slug on save."""
        # Generate slug if empty or if it's a placeholder like 'untitled'
        should_regenerate = (
            not self.slug or
            self.slug == 'untitled' or
            self.slug.startswith('untitled-')
        )

        if should_regenerate and self.title and self.title.lower() != 'untitled':
            base_slug = slugify(self.title)
            if base_slug:  # Only update if we get a valid slug
                slug = base_slug
                counter = 1
                while Listing.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1
                self.slug = slug
        elif not self.slug:
            # Fallback for empty slug
            base_slug = slugify(self.title) if self.title else 'listing'
            slug = base_slug or 'listing'
            counter = 1
            while Listing.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug or 'listing'}-{counter}"
                counter += 1
            self.slug = slug

        super().save(*args, **kwargs)

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
