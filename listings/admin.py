"""Listing admin configuration with approval workflow."""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import City, Listing, ListingImage, ListingAmenity, ListingAmenityMapping


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'province', 'country', 'is_active', 'order', 'listing_count']
    list_filter = ['is_active', 'province', 'country']
    search_fields = ['name', 'province']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'name']

    def listing_count(self, obj):
        return obj.listings.count()
    listing_count.short_description = 'Listings'


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 3
    fields = ['image', 'caption', 'is_primary', 'order']
    ordering = ['order']


class ListingAmenityMappingInline(admin.TabularInline):
    model = ListingAmenityMapping
    extra = 3
    autocomplete_fields = ['amenity']


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'host',
        'city',
        'property_category',
        'price_per_night',
        'status',
        'is_featured',
        'is_instant_bookable',
        'created_at',
    ]
    list_filter = ['status', 'property_type', 'property_category', 'city', 'is_instant_bookable', 'is_featured', 'cancellation_policy']
    search_fields = ['title', 'description', 'address', 'host__username', 'host__email']
    readonly_fields = ['ical_export_token', 'created_at', 'updated_at', 'submitted_for_review_at', 'reviewed_at']
    inlines = [ListingImageInline, ListingAmenityMappingInline]
    actions = ['approve_listings', 'reject_listings', 'feature_listings', 'unfeature_listings']
    autocomplete_fields = ['host', 'city']
    list_editable = ['is_featured']

    fieldsets = (
        ('Basic Info', {
            'fields': ('host', 'title', 'description', 'property_type', 'property_category', 'status'),
        }),
        ('Location', {
            'fields': ('city', 'address', 'neighborhood', 'postal_code', 'latitude', 'longitude'),
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'cleaning_fee', 'service_fee_percent', 'currency', 'weekly_discount', 'monthly_discount'),
        }),
        ('Capacity', {
            'fields': ('max_guests', 'bedrooms', 'beds', 'bathrooms'),
        }),
        ('Property Details', {
            'fields': ('space_description', 'guest_access', 'interaction_with_guests', 'other_things_to_note', 'neighborhood_overview', 'getting_around'),
            'classes': ('collapse',),
        }),
        ('Booking Rules', {
            'fields': ('minimum_nights', 'maximum_nights', 'check_in_time', 'check_out_time', 'cancellation_policy'),
        }),
        ('House Rules', {
            'fields': ('pets_allowed', 'smoking_allowed', 'parties_allowed', 'children_allowed', 'infants_allowed', 'additional_rules'),
        }),
        ('Settings', {
            'fields': ('is_instant_bookable', 'is_featured', 'ical_export_token'),
        }),
        ('Review Status', {
            'fields': ('submitted_for_review_at', 'reviewed_at', 'reviewed_by', 'rejection_reason'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.action(description='Approve selected listings')
    def approve_listings(self, request, queryset):
        count = queryset.filter(
            status=Listing.Status.PENDING_REVIEW
        ).update(
            status=Listing.Status.ACTIVE,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'{count} listing(s) approved and now active.')

    @admin.action(description='Reject selected listings')
    def reject_listings(self, request, queryset):
        count = queryset.filter(
            status=Listing.Status.PENDING_REVIEW
        ).update(
            status=Listing.Status.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'{count} listing(s) rejected.')

    @admin.action(description='Feature selected listings')
    def feature_listings(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} listing(s) featured.')

    @admin.action(description='Unfeature selected listings')
    def unfeature_listings(self, request, queryset):
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} listing(s) unfeatured.')


@admin.register(ListingAmenity)
class ListingAmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'icon']
    list_filter = ['category']
    search_fields = ['name']
