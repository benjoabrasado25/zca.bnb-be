"""Listing admin configuration."""

from django.contrib import admin

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
    search_fields = ['title', 'description', 'address', 'city']
    readonly_fields = ['ical_export_token', 'created_at', 'updated_at']
    inlines = [ListingImageInline, ListingAmenityMappingInline]

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
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(ListingAmenity)
class ListingAmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'icon']
    list_filter = ['category']
    search_fields = ['name']
