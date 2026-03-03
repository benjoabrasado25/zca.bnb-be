"""Integration admin configuration."""

from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import IcalSync, IcalSyncLog


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
