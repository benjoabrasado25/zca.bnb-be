"""Integration admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import IcalSync, IcalSyncLog, AirbnbSyncJob


class IcalSyncLogInline(TabularInline):
    model = IcalSyncLog
    extra = 0
    readonly_fields = ['status', 'events_found', 'events_created', 'events_updated', 'events_skipped', 'error_message', 'created_at']
    can_delete = False
    max_num = 10
    ordering = ['-created_at']


@admin.register(IcalSync)
class IcalSyncAdmin(ModelAdmin):
    list_display = [
        'listing',
        'platform',
        'status',
        'last_synced_at',
        'sync_count',
        'created_at',
    ]
    list_filter = ['platform', 'status', 'created_at']
    search_fields = ['listing__title', 'airbnb_import_url']
    readonly_fields = ['last_synced_at', 'sync_count', 'created_at', 'updated_at']
    inlines = [IcalSyncLogInline]

    fieldsets = (
        ('Configuration', {
            'fields': ('listing', 'platform', 'airbnb_import_url', 'status'),
        }),
        ('Sync Info', {
            'fields': ('last_synced_at', 'last_error', 'sync_count'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(IcalSyncLog)
class IcalSyncLogAdmin(ModelAdmin):
    list_display = [
        'ical_sync',
        'status',
        'events_found',
        'events_created',
        'events_updated',
        'created_at',
    ]
    list_filter = ['status', 'created_at']
    readonly_fields = [
        'ical_sync', 'status', 'events_found', 'events_created',
        'events_updated', 'events_skipped', 'error_message', 'created_at',
    ]


@admin.register(AirbnbSyncJob)
class AirbnbSyncJobAdmin(ModelAdmin):
    list_display = [
        'run_id',
        'status_badge',
        'listings_created',
        'listings_updated',
        'url_count',
        'created_at',
        'completed_at',
    ]
    list_filter = ['status', 'created_at']
    readonly_fields = [
        'run_id', 'airbnb_urls', 'status', 'listings_created',
        'listings_updated', 'error_message', 'created_at', 'completed_at',
    ]
    ordering = ['-created_at']

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'running': '#17a2b8',
            'succeeded': '#28a745',
            'failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def url_count(self, obj):
        if obj.airbnb_urls:
            return len(obj.airbnb_urls)
        return 0
    url_count.short_description = 'URLs'

    fieldsets = (
        ('Job Info', {
            'fields': ('run_id', 'status', 'airbnb_urls'),
        }),
        ('Results', {
            'fields': ('listings_created', 'listings_updated', 'error_message'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at'),
        }),
    )
