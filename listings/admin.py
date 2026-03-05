"""Listing admin configuration with approval workflow."""

from django.contrib import admin, messages
from django.contrib.auth.models import Group
from django.shortcuts import render, redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from rest_framework.authtoken.models import TokenProxy
from unfold.admin import ModelAdmin, TabularInline, StackedInline

from .models import City, Listing, ListingImage, ListingAmenity, ListingAmenityMapping
from bookings.models import BlockedDate
from integrations.models import IcalSync

# Hide Groups and Tokens from admin sidebar
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(TokenProxy)
except admin.sites.NotRegistered:
    pass


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

    def has_module_permission(self, request):
        """Only superusers can see Cities in sidebar."""
        return request.user.is_superuser


class ListingImageInline(TabularInline):
    model = ListingImage
    extra = 0
    fields = ['image', 'caption', 'is_primary', 'order']
    ordering = ['order']


class ListingAmenityMappingInline(TabularInline):
    model = ListingAmenityMapping
    extra = 0
    autocomplete_fields = ['amenity']


class BlockedDateInline(TabularInline):
    """Inline for managing blocked dates within a Listing."""
    model = BlockedDate
    extra = 0
    fields = ['start_date', 'end_date', 'reason']
    verbose_name = "Blocked Date"
    verbose_name_plural = "Blocked Dates (Host-defined unavailable periods)"


class IcalSyncInline(StackedInline):
    """Inline for managing iCal sync configuration within a Listing."""
    model = IcalSync
    extra = 1  # Show one empty form to add new iCal sync
    max_num = 1
    fields = ['platform', 'airbnb_import_url', 'status', 'last_synced_at', 'last_error', 'sync_count']
    readonly_fields = ['last_synced_at', 'last_error', 'sync_count']
    verbose_name = "iCal Sync Configuration"
    verbose_name_plural = "iCal Sync Configuration"
    template = 'admin/listings/listing/ical_sync_inline.html'

    def get_extra(self, request, obj=None, **kwargs):
        """Show 1 extra form only if no IcalSync exists for this listing."""
        if obj and IcalSync.objects.filter(listing=obj).exists():
            return 0
        return 1


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
    inlines = [ListingImageInline, ListingAmenityMappingInline, BlockedDateInline, IcalSyncInline]
    actions = ['submit_for_review', 'approve_listings', 'reject_listings', 'feature_listings', 'unfeature_listings', 'sync_from_airbnb']
    autocomplete_fields = ['host', 'city']
    list_editable = ['is_featured']
    change_list_template = 'admin/listings/listing/change_list.html'

    def has_module_permission(self, request):
        """All staff (including hosts) can see Listings in sidebar."""
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        """Hosts can view their own listings."""
        if request.user.is_superuser:
            return True
        if obj:
            return obj.host == request.user
        return request.user.is_staff

    def has_add_permission(self, request):
        """All staff can add listings."""
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        """Hosts can only edit their own listings."""
        if request.user.is_superuser:
            return True
        if obj:
            return obj.host == request.user
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        """Hosts can only delete their own listings."""
        if request.user.is_superuser:
            return True
        if obj:
            return obj.host == request.user
        return request.user.is_staff

    def get_queryset(self, request):
        """Hosts can only see their own listings. Superusers see all."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(host=request.user)

    def save_model(self, request, obj, form, change):
        """Auto-assign host to current user if not superuser. New listings start as DRAFT."""
        if not change and not request.user.is_superuser:
            obj.host = request.user
            obj.status = Listing.Status.DRAFT  # Hosts' new listings start as draft
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        """Hosts can't change certain fields."""
        readonly = list(self.readonly_fields)
        if not request.user.is_superuser:
            # Hosts can't change status, featured, or host assignment
            readonly.extend(['status', 'is_featured', 'host', 'reviewed_by', 'rejection_reason'])
        return readonly

    def airbnb_synced(self, obj):
        if obj.airbnb_id:
            return format_html('<span style="color: green;">&#10003; {}</span>', obj.airbnb_id)
        return format_html('<span style="color: gray;">-</span>')
    airbnb_synced.short_description = 'Airbnb'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-airbnb/', self.admin_site.admin_view(self.import_airbnb_view), name='listings_listing_import_airbnb'),
            path('calendar/', self.admin_site.admin_view(self.calendar_view), name='listings_listing_calendar'),
            path('calendar/block/', self.admin_site.admin_view(self.block_dates_view), name='listings_listing_block_dates'),
            path('calendar/unblock/<int:blocked_id>/', self.admin_site.admin_view(self.unblock_dates_view), name='listings_listing_unblock_dates'),
            path('<int:listing_id>/sync-ical/<int:ical_sync_id>', self.admin_site.admin_view(self.sync_ical_view), name='listings_listing_sync_ical'),
        ]
        return custom_urls + urls

    def sync_ical_view(self, request, listing_id, ical_sync_id):
        """Manually trigger iCal sync for a listing."""
        from integrations.models import IcalSync
        from integrations.ical_service import IcalSyncService
        import logging
        logger = logging.getLogger(__name__)

        try:
            ical_sync = IcalSync.objects.get(pk=ical_sync_id, listing_id=listing_id)
            logger.info(f"Manual sync triggered: listing={listing_id}, ical_sync={ical_sync_id}, url={ical_sync.airbnb_import_url}")

            if not ical_sync.airbnb_import_url:
                messages.error(request, 'No iCal URL configured. Please add the Airbnb iCal export URL first.')
                return redirect('admin:listings_listing_change', listing_id)

            # Run the sync
            service = IcalSyncService()
            success, message = service.sync(ical_sync)

            if success:
                # Also show the number of bookings now in the database
                from bookings.models import Booking
                booking_count = Booking.objects.filter(listing_id=listing_id, status='confirmed').count()
                messages.success(request, f'iCal sync completed: {message}. Total confirmed bookings: {booking_count}')
            else:
                messages.error(request, f'iCal sync failed: {message}')

        except IcalSync.DoesNotExist:
            messages.error(request, 'iCal sync configuration not found.')
        except Exception as e:
            logger.exception(f"Error during iCal sync: {e}")
            messages.error(request, f'Error during sync: {str(e)}')

        return redirect('admin:listings_listing_change', listing_id)

    def import_airbnb_view(self, request):
        """Sync listings from Airbnb - simple page like WordPress plugin."""
        from integrations.apify_service import AirbnbSyncService

        apify_configured = bool(AirbnbSyncService.get_api_token())
        last_sync = None

        # Handle sync all existing listings
        if request.method == 'POST' and request.GET.get('sync_all'):
            if not apify_configured:
                messages.error(request, 'APIFY_TOKEN is not configured.')
                return redirect('admin:listings_listing_import_airbnb')

            # Get all listings with airbnb_url
            existing = Listing.objects.exclude(airbnb_url='').exclude(airbnb_url__isnull=True)
            urls = [l.airbnb_url for l in existing if l.airbnb_url]

            if not urls:
                messages.warning(request, 'No existing listings with Airbnb URLs found.')
                return redirect('admin:listings_listing_import_airbnb')

            try:
                results = AirbnbSyncService.sync_and_wait(urls, host=request.user, timeout=600)
                if results['success']:
                    messages.success(request, f"Synced {results['updated']} existing listing(s).")
                else:
                    for error in results.get('errors', []):
                        messages.error(request, error)
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')

            return redirect('admin:listings_listing_import_airbnb')

        # Handle new URL sync
        if request.method == 'POST' and request.POST.get('airbnb_urls'):
            if not apify_configured:
                messages.error(request, 'APIFY_TOKEN is not configured.')
                return redirect('admin:listings_listing_import_airbnb')

            urls_text = request.POST.get('airbnb_urls', '')
            urls = [url.strip() for url in urls_text.strip().split('\n') if url.strip() and 'airbnb.com' in url]

            if not urls:
                messages.error(request, 'Please enter at least one valid Airbnb URL.')
                return redirect('admin:listings_listing_import_airbnb')

            try:
                results = AirbnbSyncService.sync_and_wait(urls, host=request.user, timeout=300)

                if results['success']:
                    msg = f"Successfully synced {results['created']} new listing(s)"
                    if results['updated']:
                        msg += f" and updated {results['updated']} existing listing(s)"
                    messages.success(request, msg)
                    return redirect('admin:listings_listing_changelist')
                else:
                    for error in results.get('errors', []):
                        messages.error(request, error)

            except Exception as e:
                messages.error(request, f'Error during sync: {str(e)}')

            return redirect('admin:listings_listing_import_airbnb')

        # Get last sync time
        last_synced = Listing.objects.exclude(last_synced__isnull=True).order_by('-last_synced').first()
        if last_synced and last_synced.last_synced:
            last_sync = last_synced.last_synced.strftime('%b %d, %Y %I:%M %p')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Sync Listings from Airbnb',
            'opts': self.model._meta,
            'apify_configured': apify_configured,
            'last_sync': last_sync,
        }
        return render(request, 'admin/listings/listing/import_airbnb.html', context)

    def calendar_view(self, request):
        """Calendar view for hosts to manage blocked dates across all their listings."""
        from datetime import date, timedelta
        from bookings.models import Booking
        import json

        # Get listings for current user (or all for superuser)
        if request.user.is_superuser:
            listings = Listing.objects.all().prefetch_related('blocked_dates', 'bookings', 'images')
        else:
            listings = Listing.objects.filter(host=request.user).prefetch_related('blocked_dates', 'bookings', 'images')

        # Get date range (default: current month + 2 months)
        today = date.today()
        start_date = today.replace(day=1)
        # Show 3 months
        if start_date.month <= 10:
            end_date = start_date.replace(month=start_date.month + 2, day=28)
        else:
            end_date = start_date.replace(year=start_date.year + 1, month=(start_date.month + 2) % 12 or 12, day=28)

        # Build calendar data for each listing
        calendar_data = []
        for listing in listings:
            # Get primary image
            primary_image = listing.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = listing.images.first()

            # Get bookings (confirmed/pending)
            bookings = Booking.objects.filter(
                listing=listing,
                status__in=['confirmed', 'pending'],
                check_out__gte=start_date,
                check_in__lte=end_date,
            ).values('id', 'check_in', 'check_out', 'guest_name', 'status', 'source')

            # Get blocked dates
            blocked = BlockedDate.objects.filter(
                listing=listing,
                end_date__gte=start_date,
                start_date__lte=end_date,
            ).values('id', 'start_date', 'end_date', 'reason')

            calendar_data.append({
                'listing': listing,
                'image': primary_image,
                'bookings': list(bookings),
                'blocked_dates': list(blocked),
            })

        # Generate date headers
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current)
            current += timedelta(days=1)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Calendar - Manage Availability',
            'opts': self.model._meta,
            'calendar_data': calendar_data,
            'dates': dates,
            'today': today,
            'start_date': start_date,
            'end_date': end_date,
            'listings_json': json.dumps([{'id': l.id, 'title': l.title} for l in listings]),
        }
        return render(request, 'admin/listings/listing/calendar.html', context)

    def block_dates_view(self, request):
        """Handle blocking dates via POST."""
        from datetime import datetime

        if request.method == 'POST':
            listing_id = request.POST.get('listing_id')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            reason = request.POST.get('reason', '')

            try:
                # Verify ownership
                if request.user.is_superuser:
                    listing = Listing.objects.get(id=listing_id)
                else:
                    listing = Listing.objects.get(id=listing_id, host=request.user)

                BlockedDate.objects.create(
                    listing=listing,
                    start_date=datetime.strptime(start_date, '%Y-%m-%d').date(),
                    end_date=datetime.strptime(end_date, '%Y-%m-%d').date(),
                    reason=reason,
                )
                messages.success(request, f'Dates blocked for {listing.title}')
            except Listing.DoesNotExist:
                messages.error(request, 'Listing not found or access denied.')
            except Exception as e:
                messages.error(request, f'Error: {str(e)}')

        return redirect('admin:listings_listing_calendar')

    def unblock_dates_view(self, request, blocked_id):
        """Remove a blocked date range."""
        try:
            if request.user.is_superuser:
                blocked = BlockedDate.objects.get(id=blocked_id)
            else:
                blocked = BlockedDate.objects.get(id=blocked_id, listing__host=request.user)

            listing_title = blocked.listing.title
            blocked.delete()
            messages.success(request, f'Unblocked dates for {listing_title}')
        except BlockedDate.DoesNotExist:
            messages.error(request, 'Blocked date not found or access denied.')

        return redirect('admin:listings_listing_calendar')

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

    def get_actions(self, request):
        """Filter actions based on user type."""
        actions = super().get_actions(request)
        if not request.user.is_superuser:
            # Hosts can only submit for review, not approve/reject/feature
            allowed = ['submit_for_review']
            actions = {k: v for k, v in actions.items() if k in allowed or k == 'delete_selected'}
        return actions

    @admin.action(description='📝 Submit for Review')
    def submit_for_review(self, request, queryset):
        """Host action to submit draft listings for admin review."""
        count = queryset.filter(
            status=Listing.Status.DRAFT
        ).update(
            status=Listing.Status.PENDING_REVIEW,
            submitted_for_review_at=timezone.now(),
        )
        if count:
            self.message_user(request, f'{count} listing(s) submitted for review. Admin will approve shortly.')
        else:
            self.message_user(request, 'No draft listings selected.', level=messages.WARNING)

    @admin.action(description='✅ Approve selected listings')
    def approve_listings(self, request, queryset):
        count = queryset.filter(
            status=Listing.Status.PENDING_REVIEW
        ).update(
            status=Listing.Status.ACTIVE,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'{count} listing(s) approved and now active.')

    @admin.action(description='❌ Reject selected listings')
    def reject_listings(self, request, queryset):
        count = queryset.filter(
            status=Listing.Status.PENDING_REVIEW
        ).update(
            status=Listing.Status.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user,
        )
        self.message_user(request, f'{count} listing(s) rejected.')

    @admin.action(description='⭐ Feature selected listings')
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

    def has_module_permission(self, request):
        """Only superusers can see Amenities in sidebar."""
        return request.user.is_superuser
