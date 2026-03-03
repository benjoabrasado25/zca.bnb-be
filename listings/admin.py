"""Listing admin configuration with approval workflow."""

from django.contrib import admin
from django.utils import timezone

from .models import Listing, ListingImage, ListingAmenity, ListingAmenityMapping


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


class ListingAmenityMappingInline(admin.TabularInline):
    model = ListingAmenityMapping
    extra = 1


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'host',
        'city',
        'price_per_night',
        'status',
        'is_instant_bookable',
        'created_at',
    ]
    list_filter = ['status', 'property_type', 'city', 'is_instant_bookable']
    search_fields = ['title', 'description', 'address', 'city', 'host__username', 'host__email']
    readonly_fields = ['ical_export_token', 'created_at', 'updated_at', 'submitted_for_review_at', 'reviewed_at']
    inlines = [ListingImageInline, ListingAmenityMappingInline]
    actions = ['approve_listings', 'reject_listings']

    fieldsets = (
        ('Basic Info', {
            'fields': ('host', 'title', 'description', 'property_type', 'status'),
        }),
        ('Location', {
            'fields': ('address', 'city', 'province', 'postal_code', 'country', 'latitude', 'longitude'),
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'cleaning_fee', 'currency'),
        }),
        ('Capacity', {
            'fields': ('max_guests', 'bedrooms', 'beds', 'bathrooms'),
        }),
        ('Rules', {
            'fields': ('minimum_nights', 'maximum_nights', 'check_in_time', 'check_out_time'),
        }),
        ('Settings', {
            'fields': ('is_instant_bookable', 'ical_export_token'),
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


@admin.register(ListingAmenity)
class ListingAmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'icon']
    list_filter = ['category']
    search_fields = ['name']
