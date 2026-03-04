"""Integration admin configuration."""

from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import IcalSync, IcalSyncLog


class IcalSyncLogInline(TabularInline):
    """Inline for viewing sync logs within IcalSync."""
    model = IcalSyncLog
    extra = 0
    readonly_fields = ['status', 'events_found', 'events_created', 'events_updated', 'events_skipped', 'error_message', 'created_at']
    can_delete = False
    max_num = 5
    ordering = ['-created_at']


# Note: IcalSync is now managed as an inline within the Listing admin
# These models are kept registered but hidden from the sidebar for direct access if needed

# Unregister from sidebar - managed via Listing inline instead
# If you need to access these directly, you can still go to /admin/integrations/icalsync/
