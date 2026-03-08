"""Integration admin configuration."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import action

from users.models import User
from .models import IcalSync, IcalSyncLog, AirbnbSyncJob, AmadeusSyncJob
from .amadeus_service import AmadeusHotelService, PHILIPPINE_CITY_CODES


class IcalSyncLogInline(TabularInline):
    """Inline for viewing sync logs within IcalSync."""
    model = IcalSyncLog
    extra = 0
    readonly_fields = ['status', 'events_found', 'events_created', 'events_updated', 'events_skipped', 'error_message', 'created_at']
    can_delete = False
    max_num = 5
    ordering = ['-created_at']


@admin.register(AirbnbSyncJob)
class AirbnbSyncJobAdmin(ModelAdmin):
    """Admin for Airbnb sync jobs."""
    list_display = ['run_id', 'status', 'listings_created', 'listings_updated', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['run_id']
    readonly_fields = ['run_id', 'airbnb_urls', 'status', 'listings_created', 'listings_updated', 'error_message', 'raw_response', 'created_at', 'completed_at']
    ordering = ['-created_at']


@admin.register(AmadeusSyncJob)
class AmadeusSyncJobAdmin(ModelAdmin):
    """Admin for Amadeus sync jobs with sync actions."""

    list_display = [
        'job_id',
        'sync_type',
        'city_code',
        'status',
        'hotels_found',
        'hotels_created',
        'hotels_updated',
        'created_at',
    ]
    list_filter = ['status', 'sync_type', 'city_code', 'created_at']
    search_fields = ['job_id', 'city_code']
    readonly_fields = [
        'job_id', 'sync_type', 'city_code', 'latitude', 'longitude', 'radius',
        'status', 'hotels_found', 'hotels_created', 'hotels_updated',
        'error_message', 'raw_response', 'created_at', 'completed_at',
    ]
    ordering = ['-created_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync-city/',
                self.admin_site.admin_view(self.sync_city_view),
                name='integrations_amadeus_sync_city',
            ),
            path(
                'sync-all/',
                self.admin_site.admin_view(self.sync_all_view),
                name='integrations_amadeus_sync_all',
            ),
            path(
                'test-connection/',
                self.admin_site.admin_view(self.test_connection_view),
                name='integrations_amadeus_test_connection',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['philippine_cities'] = PHILIPPINE_CITY_CODES
        extra_context['show_sync_buttons'] = True
        return super().changelist_view(request, extra_context=extra_context)

    def test_connection_view(self, request):
        """Test Amadeus API connection."""
        success, message = AmadeusHotelService.test_connection()
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return HttpResponseRedirect(reverse('admin:integrations_amadeussyncjob_changelist'))

    def sync_city_view(self, request):
        """Sync hotels for a specific city."""
        if request.method == 'POST':
            city_code = request.POST.get('city_code')
            if not city_code:
                messages.error(request, "Please select a city")
                return HttpResponseRedirect(reverse('admin:integrations_amadeussyncjob_changelist'))

            # Get admin user as host (or create a system user)
            host = request.user

            result = AmadeusHotelService.sync_city(city_code, host)

            if result['success']:
                messages.success(
                    request,
                    f"Synced {result['found']} hotels for {city_code}: "
                    f"{result['created']} created, {result['updated']} updated"
                )
            else:
                messages.error(request, f"Sync failed: {', '.join(result['errors'])}")

            return HttpResponseRedirect(reverse('admin:integrations_amadeussyncjob_changelist'))

        # Show city selection form
        context = {
            'title': 'Sync Hotels by City',
            'philippine_cities': PHILIPPINE_CITY_CODES,
            'opts': self.model._meta,
        }
        return render(request, 'admin/integrations/amadeus_sync_city.html', context)

    def sync_all_view(self, request):
        """Sync hotels for all Philippine cities."""
        if request.method == 'POST':
            host = request.user

            result = AmadeusHotelService.sync_all_philippine_cities(host)

            messages.success(
                request,
                f"Synced {result['cities_synced']} cities: "
                f"{result['total_found']} hotels found, "
                f"{result['total_created']} created, {result['total_updated']} updated"
            )

            if result['errors']:
                messages.warning(request, f"Some errors occurred: {', '.join(result['errors'][:5])}")

            return HttpResponseRedirect(reverse('admin:integrations_amadeussyncjob_changelist'))

        # Confirmation page
        context = {
            'title': 'Sync All Philippine Cities',
            'philippine_cities': PHILIPPINE_CITY_CODES,
            'opts': self.model._meta,
        }
        return render(request, 'admin/integrations/amadeus_sync_all.html', context)


# Note: IcalSync is now managed as an inline within the Listing admin
# These models are kept registered but hidden from the sidebar for direct access if needed
