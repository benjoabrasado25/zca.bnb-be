"""Booking admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Booking, BlockedDate


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    """Admin for site bookings only (excludes iCal imports)."""

    def has_module_permission(self, request):
        """Only superusers can see Bookings in sidebar."""
        return request.user.is_superuser

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

    def get_queryset(self, request):
        """Only show bookings made on the site (MANUAL source), not iCal imports."""
        qs = super().get_queryset(request)
        return qs.filter(source=Booking.Source.MANUAL)

    fieldsets = (
        ('Booking Info', {
            'fields': ('listing', 'guest', 'status', 'source'),
        }),
        ('Dates', {
            'fields': ('check_in', 'check_out'),
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'cleaning_fee', 'service_fee', 'total_price', 'currency'),
        }),
        ('Guest Details', {
            'fields': ('num_guests', 'guest_name', 'guest_email', 'guest_phone'),
        }),
        ('Notes', {
            'fields': ('special_requests', 'host_notes'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'cancelled_at'),
        }),
    )


# BlockedDate is now managed as inline in Listing admin
# Unregister standalone admin
# admin.site.unregister(BlockedDate)  # Don't register it at all
