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
                'browse-hotels/',
                self.admin_site.admin_view(self.sync_city_view),
                name='integrations_amadeus_sync_city',
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
        """Browse hotels from Amadeus and selectively import."""
        city_code = request.GET.get('city_code') or request.POST.get('city_code')

        # Step 3: Import selected hotels only
        if request.method == 'POST' and request.POST.get('import_selected') == 'yes':
            selected_ids = request.POST.getlist('hotel_ids')
            if not selected_ids:
                messages.error(request, "No hotels selected")
                return HttpResponseRedirect(reverse('admin:integrations_amadeus_sync_city'))

            # Fetch hotels again to get full data
            hotels, error = AmadeusHotelService.fetch_hotels_by_city(city_code)
            if error:
                messages.error(request, f"Failed to fetch hotels: {error}")
                return HttpResponseRedirect(reverse('admin:integrations_amadeus_sync_city'))

            # Filter to only selected hotels
            selected_hotels = [h for h in hotels if h.get('hotelId') in selected_ids]

            # Import selected hotels
            host = request.user
            created = 0
            updated = 0
            city_name = PHILIPPINE_CITY_CODES.get(city_code, city_code)
            from listings.models import City
            city, _ = City.objects.get_or_create(name=city_name, defaults={'country': 'Philippines'})

            for hotel_data in selected_hotels:
                listing, status = AmadeusHotelService.process_hotel_data(hotel_data, host, city)
                if status == 'created':
                    created += 1
                elif status == 'updated':
                    updated += 1

            messages.success(request, f"Imported {created + updated} hotels: {created} created, {updated} updated")
            return HttpResponseRedirect(reverse('admin:listings_listing_changelist') + '?status__exact=draft')

        # Step 2: Show hotels with checkboxes for selection
        if request.method == 'POST' and city_code:
            hotels, error = AmadeusHotelService.fetch_hotels_by_city(city_code)

            if error:
                messages.error(request, f"Failed to fetch hotels: {error}")
                return HttpResponseRedirect(reverse('admin:integrations_amadeus_sync_city'))

            # Check which hotels already exist
            from listings.models import Listing
            existing_ids = set(Listing.objects.filter(
                amadeus_hotel_id__in=[h.get('hotelId') for h in hotels]
            ).values_list('amadeus_hotel_id', flat=True))

            for hotel in hotels:
                hotel['already_exists'] = hotel.get('hotelId') in existing_ids

            context = {
                'title': f'Browse Hotels - {PHILIPPINE_CITY_CODES.get(city_code, city_code)}',
                'city_code': city_code,
                'city_name': PHILIPPINE_CITY_CODES.get(city_code, city_code),
                'hotels': hotels,
                'hotels_count': len(hotels),
                'new_hotels_count': len([h for h in hotels if not h.get('already_exists')]),
                'opts': self.model._meta,
                'show_hotels': True,
            }
            return render(request, 'admin/integrations/amadeus_sync_city.html', context)

        # Step 1: Show city selection form
        context = {
            'title': 'Browse Hotels from Amadeus',
            'philippine_cities': PHILIPPINE_CITY_CODES,
            'opts': self.model._meta,
            'show_hotels': False,
        }
        return render(request, 'admin/integrations/amadeus_sync_city.html', context)



# Note: IcalSync is now managed as an inline within the Listing admin
# These models are kept registered but hidden from the sidebar for direct access if needed
