"""Listing admin configuration with approval workflow."""

from django import forms
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import City, Listing, ListingImage, ListingAmenity, ListingAmenityMapping


class AirbnbImportForm(forms.Form):
    """Form for importing listings from Airbnb URLs."""
    airbnb_urls = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'placeholder': 'Enter Airbnb URLs, one per line\n\nhttps://www.airbnb.com/rooms/12345678\nhttps://www.airbnb.com/rooms/87654321'}),
        label='Airbnb URLs',
        help_text='Enter one Airbnb listing URL per line. The system will scrape and import the listing data.',
    )


@admin.register(City)
class CityAdmin(ModelAdmin):
    list_display = ['name', 'province', 'country', 'is_active', 'order', 'listing_count']
    list_filter = ['is_active', 'province', 'country']
    search_fields = ['name', 'province']
    list_editable = ['is_active', 'order']
    ordering = ['order', 'name']

    def listing_count(self, obj):
        return obj.listings.count()
    listing_count.short_description = 'Listings'


class ListingImageInline(TabularInline):
    model = ListingImage
    extra = 3
    fields = ['image', 'caption', 'is_primary', 'order']
    ordering = ['order']


class ListingAmenityMappingInline(TabularInline):
    model = ListingAmenityMapping
    extra = 3
    autocomplete_fields = ['amenity']


@admin.register(Listing)
class ListingAdmin(ModelAdmin):
    list_display = [
        'title',
        'host',
        'city',
        'property_category',
        'price_per_night',
        'status',
        'is_featured',
        'is_instant_bookable',
        'airbnb_synced',
        'created_at',
    ]
    list_filter = ['status', 'property_type', 'property_category', 'city', 'is_instant_bookable', 'is_featured', 'cancellation_policy']
    search_fields = ['title', 'description', 'address', 'host__username', 'host__email', 'airbnb_id']
    readonly_fields = ['ical_export_token', 'created_at', 'updated_at', 'submitted_for_review_at', 'reviewed_at', 'airbnb_id', 'last_synced']
    inlines = [ListingImageInline, ListingAmenityMappingInline]
    actions = ['approve_listings', 'reject_listings', 'feature_listings', 'unfeature_listings', 'sync_from_airbnb']
    autocomplete_fields = ['host', 'city']
    list_editable = ['is_featured']
    change_list_template = 'admin/listings/listing/change_list.html'

    def airbnb_synced(self, obj):
        if obj.airbnb_id:
            return format_html('<span style="color: green;">&#10003; {}</span>', obj.airbnb_id)
        return format_html('<span style="color: gray;">-</span>')
    airbnb_synced.short_description = 'Airbnb'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-airbnb/', self.admin_site.admin_view(self.import_airbnb_view), name='listings_listing_import_airbnb'),
        ]
        return custom_urls + urls

    def import_airbnb_view(self, request):
        """Custom admin view for importing listings from Airbnb."""
        if request.method == 'POST':
            form = AirbnbImportForm(request.POST)
            if form.is_valid():
                urls_text = form.cleaned_data['airbnb_urls']
                urls = [url.strip() for url in urls_text.strip().split('\n') if url.strip() and 'airbnb.com' in url]

                if not urls:
                    messages.error(request, 'Please enter at least one valid Airbnb URL.')
                    return redirect('admin:listings_listing_import_airbnb')

                try:
                    from integrations.apify_service import AirbnbSyncService

                    # Check if APIFY is configured
                    if not AirbnbSyncService.get_api_token():
                        messages.error(request, 'APIFY_TOKEN is not configured. Please add it to your environment variables.')
                        return redirect('admin:listings_listing_import_airbnb')

                    # Run sync and wait for results (this may take 1-5 minutes)
                    results = AirbnbSyncService.sync_and_wait(urls, host=request.user, timeout=300)

                    if results['success']:
                        msg = f"Successfully synced {results['created']} new listing(s)"
                        if results['updated']:
                            msg += f" and updated {results['updated']} existing listing(s)"
                        messages.success(request, msg)
                    else:
                        if results['errors']:
                            for error in results['errors']:
                                messages.error(request, error)
                        else:
                            messages.error(request, 'Sync failed. Check Airbnb Sync Jobs for details.')

                    return redirect('admin:listings_listing_changelist')

                except ImportError as e:
                    messages.error(request, f'Integration module error: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Error during sync: {str(e)}')

                return redirect('admin:listings_listing_import_airbnb')
        else:
            form = AirbnbImportForm()

        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'title': 'Sync from Airbnb',
            'opts': self.model._meta,
        }
        return render(request, 'admin/listings/listing/import_airbnb.html', context)

    fieldsets = (
        ('Basic Info', {
            'fields': ('host', 'title', 'description', 'property_type', 'property_category', 'status'),
        }),
        ('Location', {
            'fields': ('city', 'address', 'neighborhood', 'postal_code', 'latitude', 'longitude'),
        }),
        ('Pricing', {
            'fields': ('price_per_night', 'cleaning_fee', 'service_fee_percent', 'currency', 'weekly_discount', 'monthly_discount'),
        }),
        ('Capacity', {
            'fields': ('max_guests', 'bedrooms', 'beds', 'bathrooms'),
        }),
        ('Property Details', {
            'fields': ('space_description', 'guest_access', 'interaction_with_guests', 'other_things_to_note', 'neighborhood_overview', 'getting_around'),
            'classes': ('collapse',),
        }),
        ('Booking Rules', {
            'fields': ('minimum_nights', 'maximum_nights', 'check_in_time', 'check_out_time', 'cancellation_policy'),
        }),
        ('House Rules', {
            'fields': ('pets_allowed', 'smoking_allowed', 'parties_allowed', 'children_allowed', 'infants_allowed', 'additional_rules'),
        }),
        ('Settings', {
            'fields': ('is_instant_bookable', 'is_featured', 'ical_export_token'),
        }),
        ('Airbnb Integration', {
            'fields': ('airbnb_id', 'airbnb_url', 'booking_url', 'last_synced'),
            'classes': ('collapse',),
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

    @admin.action(description='Feature selected listings')
    def feature_listings(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} listing(s) featured.')

    @admin.action(description='Unfeature selected listings')
    def unfeature_listings(self, request, queryset):
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} listing(s) unfeatured.')

    @admin.action(description='Re-sync selected listings from Airbnb')
    def sync_from_airbnb(self, request, queryset):
        """Re-sync selected listings that have Airbnb URLs."""
        urls = []
        for listing in queryset:
            if listing.airbnb_url:
                urls.append(listing.airbnb_url)
            elif listing.airbnb_id:
                urls.append(f'https://www.airbnb.com/rooms/{listing.airbnb_id}')

        if not urls:
            self.message_user(request, 'No listings with Airbnb URLs/IDs selected.', level=messages.WARNING)
            return

        try:
            from integrations.apify_service import ApifyService

            if not ApifyService.get_api_token():
                self.message_user(request, 'APIFY_TOKEN is not configured.', level=messages.ERROR)
                return

            run_id, error = ApifyService.start_sync_job(urls)

            if error:
                self.message_user(request, f'Failed to start sync: {error}', level=messages.ERROR)
            else:
                self.message_user(request, f'Sync job started for {len(urls)} listing(s). Job ID: {run_id}')
        except Exception as e:
            self.message_user(request, f'Error: {str(e)}', level=messages.ERROR)


@admin.register(ListingAmenity)
class ListingAmenityAdmin(ModelAdmin):
    list_display = ['name', 'category', 'icon']
    list_filter = ['category']
    search_fields = ['name']
