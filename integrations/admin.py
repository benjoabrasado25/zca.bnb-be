"""Integration admin configuration."""

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import IcalSync, IcalSyncLog, AirbnbSyncJob, GooglePlacesSyncJob
from .google_places_service import GooglePlacesService, PHILIPPINE_CITIES


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


@admin.register(GooglePlacesSyncJob)
class GooglePlacesSyncJobAdmin(ModelAdmin):
    """Admin for Google Places sync jobs."""

    list_display = [
        'job_id',
        'city_name',
        'search_query',
        'status',
        'hotels_found',
        'hotels_created',
        'hotels_updated',
        'created_at',
    ]
    list_filter = ['status', 'city_name', 'created_at']
    search_fields = ['job_id', 'city_name', 'search_query']
    readonly_fields = [
        'job_id', 'search_query', 'city_name',
        'status', 'hotels_found', 'hotels_created', 'hotels_updated',
        'error_message', 'created_at', 'completed_at',
    ]
    ordering = ['-created_at']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'browse-hotels/',
                self.admin_site.admin_view(self.browse_hotels_view),
                name='integrations_google_browse_hotels',
            ),
            path(
                'test-connection/',
                self.admin_site.admin_view(self.test_connection_view),
                name='integrations_google_test_connection',
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['philippine_cities'] = PHILIPPINE_CITIES
        return super().changelist_view(request, extra_context=extra_context)

    def test_connection_view(self, request):
        """Test Google Places API connection."""
        success, message = GooglePlacesService.test_connection()
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return HttpResponseRedirect(reverse('admin:integrations_googleplacessyncjob_changelist'))

    def browse_hotels_view(self, request):
        """Browse and import hotels from Google Places."""
        city_name = request.GET.get('city_name') or request.POST.get('city_name')
        custom_query = request.POST.get('custom_query', '').strip()

        # Step 3: Import selected hotels
        if request.method == 'POST' and request.POST.get('import_selected') == 'yes':
            selected_ids = request.POST.getlist('place_ids')
            download_images = request.POST.get('download_images') == 'on'

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Import request - selected_ids: {selected_ids}, download_images: {download_images}")

            if not selected_ids:
                messages.error(request, "No hotels selected")
                return HttpResponseRedirect(reverse('admin:integrations_google_browse_hotels'))

            # Search again to get full data
            query = custom_query or f"hotels in {city_name}, Philippines"
            places, error = GooglePlacesService.search_hotels(query)
            if error:
                messages.error(request, f"Failed to fetch hotels: {error}")
                return HttpResponseRedirect(reverse('admin:integrations_google_browse_hotels'))

            # Filter to selected places
            selected_places = [p for p in places if p.get('id') in selected_ids]

            if not selected_places:
                messages.error(request, f"No matching places found. Selected IDs: {selected_ids[:3]}... Found IDs: {[p.get('id')[:20] for p in places[:3]]}...")
                return HttpResponseRedirect(reverse('admin:integrations_google_browse_hotels'))

            # Get or create city
            from listings.models import City
            city = None
            if city_name:
                city, _ = City.objects.get_or_create(
                    name=city_name,
                    defaults={'country': 'Philippines'}
                )

            # Import selected
            host = request.user
            created = 0
            updated = 0

            errors = []
            for place_data in selected_places:
                # Get full details for each place
                details, detail_error = GooglePlacesService.get_place_details(place_data.get('id'))
                if details:
                    place_data.update(details)
                elif detail_error:
                    errors.append(f"Details error for {place_data.get('id')}: {detail_error}")

                listing, status = GooglePlacesService.process_place_to_listing(
                    place_data, host, city, download_images
                )
                if status == 'created':
                    created += 1
                elif status == 'updated':
                    updated += 1
                elif status.startswith('error:'):
                    errors.append(status)

            if errors:
                messages.warning(request, f"Errors during import: {'; '.join(errors[:3])}")

            messages.success(
                request,
                f"Imported {created + updated} hotels: {created} created, {updated} updated"
            )
            return HttpResponseRedirect(reverse('admin:listings_listing_changelist') + '?status__exact=draft')

        # Step 2: Show hotels with checkboxes
        if request.method == 'POST' and (city_name or custom_query):
            query = custom_query or f"hotels in {city_name}, Philippines"
            places, error = GooglePlacesService.search_hotels(query)

            if error:
                messages.error(request, f"Failed to fetch hotels: {error}")
                return HttpResponseRedirect(reverse('admin:integrations_google_browse_hotels'))

            # Check which already exist
            from listings.models import Listing
            existing_ids = set(Listing.objects.filter(
                google_place_id__in=[p.get('id') for p in places]
            ).values_list('google_place_id', flat=True))

            for place in places:
                place['already_exists'] = place.get('id') in existing_ids
                # Extract display name
                display_name = place.get('displayName', {})
                place['name'] = display_name.get('text', 'Unknown') if isinstance(display_name, dict) else str(display_name)
                # Get photo preview URL
                photos = place.get('photos', [])
                if photos:
                    place['preview_photo'] = GooglePlacesService.get_photo_url(photos[0].get('name'), max_width=200)

            context = {
                'title': f'Browse Hotels - {city_name or "Custom Search"}',
                'city_name': city_name,
                'custom_query': custom_query,
                'places': places,
                'places_count': len(places),
                'new_places_count': len([p for p in places if not p.get('already_exists')]),
                'opts': self.model._meta,
                'show_places': True,
            }
            return render(request, 'admin/integrations/google_browse_hotels.html', context)

        # Step 1: City/query selection
        context = {
            'title': 'Browse Hotels from Google Places',
            'philippine_cities': PHILIPPINE_CITIES,
            'opts': self.model._meta,
            'show_places': False,
        }
        return render(request, 'admin/integrations/google_browse_hotels.html', context)
