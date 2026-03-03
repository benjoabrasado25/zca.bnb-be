"""Booking admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Booking, BlockedDate


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = [
        'id',
        'listing',
        'guest',
        'check_in',
        'check_out',
        'total_price',
        'status',
        'source',
        'created_at',
    ]
    list_filter = ['status', 'source', 'created_at']
    search_fields = [
        'listing__title',
        'guest__email',
        'guest_name',
        'guest_email',
    ]
    readonly_fields = ['created_at', 'updated_at', 'confirmed_at', 'cancelled_at']
    date_hierarchy = 'check_in'

    fieldsets = (
        ('Booking Info', {
            'fields': ('listing', 'guest', 'status', 'source'),
        }),
        ('Dates', {
            'fields': ('check_in', 'check_out'),
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'cleaning_fee', 'total_price', 'currency'),
        }),
        ('Guest Details', {
            'fields': ('num_guests', 'guest_name', 'guest_email', 'guest_phone'),
        }),
        ('Notes', {
            'fields': ('special_requests', 'host_notes'),
        }),
        ('iCal', {
            'fields': ('external_uid',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'cancelled_at'),
        }),
    )


@admin.register(BlockedDate)
class BlockedDateAdmin(ModelAdmin):
    list_display = ['listing', 'start_date', 'end_date', 'reason', 'created_at']
    list_filter = ['created_at']
    search_fields = ['listing__title', 'reason']
