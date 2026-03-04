"""Listing views for StaySuitePH with proper permissions."""

from datetime import datetime
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from bookings.models import Booking, BlockedDate
from bookings.services import BookingService
from .models import City, Listing, ListingImage, ListingAmenity
from .serializers import (
    CitySerializer,
    ListingListSerializer,
    ListingDetailSerializer,
    ListingCreateUpdateSerializer,
    ListingImageSerializer,
    ListingAmenitySerializer,
)


class IsHostOrReadOnly(permissions.BasePermission):
    """
    Custom permission:
    - Read access: Everyone (public listings)
    - Write access: Authenticated users
    - Object-level: Only the host can edit their own listings
    """

    def has_permission(self, request, view):
        # Allow read access to everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write access requires authentication
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Allow read access to everyone
        if request.method in permissions.SAFE_METHODS:
            return True
        # Write access only for the host
        return obj.host == request.user


class IsHost(permissions.BasePermission):
    """Permission that requires user to be a host."""

    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.is_host
        )


class ListingFilter(filters.FilterSet):
    """Filter set for listings."""

    min_price = filters.NumberFilter(field_name='price_per_night', lookup_expr='gte')
    max_price = filters.NumberFilter(field_name='price_per_night', lookup_expr='lte')
    min_guests = filters.NumberFilter(field_name='max_guests', lookup_expr='gte')
    guests = filters.NumberFilter(field_name='max_guests', lookup_expr='gte')  # Alias for min_guests
    adults = filters.NumberFilter(method='filter_by_total_guests')
    children = filters.NumberFilter(method='filter_by_total_guests')
    bedrooms = filters.NumberFilter(field_name='bedrooms', lookup_expr='gte')
    beds = filters.NumberFilter(field_name='beds', lookup_expr='gte')
    bathrooms = filters.NumberFilter(field_name='bathrooms', lookup_expr='gte')
    city = filters.NumberFilter(field_name='city_id')
    city_name = filters.CharFilter(field_name='city__name', lookup_expr='icontains')
    province = filters.CharFilter(field_name='city__province', lookup_expr='icontains')
    property_type = filters.ChoiceFilter(choices=Listing.PropertyType.choices)
    property_category = filters.ChoiceFilter(choices=Listing.PropertyCategory.choices)
    instant_bookable = filters.BooleanFilter(field_name='is_instant_bookable')
    featured = filters.BooleanFilter(field_name='is_featured')

    # Date availability filters (support both snake_case and camelCase)
    check_in = filters.DateFilter(method='filter_availability')
    check_out = filters.DateFilter(method='filter_availability')
    checkIn = filters.DateFilter(method='filter_availability')
    checkOut = filters.DateFilter(method='filter_availability')

    class Meta:
        model = Listing
        fields = [
            'city', 'city_name', 'province', 'property_type', 'property_category',
            'min_price', 'max_price', 'min_guests', 'guests', 'adults', 'children',
            'bedrooms', 'beds', 'bathrooms', 'instant_bookable', 'featured',
            'check_in', 'check_out', 'checkIn', 'checkOut',
        ]

    def filter_by_total_guests(self, queryset, name, value):
        """Filter by total guests (adults + children)."""
        adults = int(self.data.get('adults', 0) or 0)
        children = int(self.data.get('children', 0) or 0)
        total_guests = adults + children

        if total_guests > 0:
            return queryset.filter(max_guests__gte=total_guests)
        return queryset

    def filter_availability(self, queryset, name, value):
        """
        Filter listings by date availability.
        Excludes listings that have conflicting bookings or blocked dates.
        """
        check_in = self.data.get('check_in') or self.data.get('checkIn')
        check_out = self.data.get('check_out') or self.data.get('checkOut')

        if not check_in or not check_out:
            return queryset

        # Parse dates if they're strings
        if isinstance(check_in, str):
            check_in = datetime.strptime(check_in, '%Y-%m-%d').date()
        if isinstance(check_out, str):
            check_out = datetime.strptime(check_out, '%Y-%m-%d').date()

        # Find listings with conflicting bookings
        conflicting_booking_listings = Booking.objects.filter(
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
            check_in__lt=check_out,
            check_out__gt=check_in,
        ).values_list('listing_id', flat=True)

        # Find listings with conflicting blocked dates
        conflicting_blocked_listings = BlockedDate.objects.filter(
            start_date__lt=check_out,
            end_date__gt=check_in,
        ).values_list('listing_id', flat=True)

        # Exclude listings with conflicts
        excluded_ids = set(conflicting_booking_listings) | set(conflicting_blocked_listings)

        # Also check the booked_dates JSON field on listings
        for listing in queryset:
            if listing.booked_dates:
                for period in listing.booked_dates:
                    period_start = period.get('start')
                    period_end = period.get('end')
                    if period_start and period_end:
                        if isinstance(period_start, str):
                            period_start = datetime.strptime(period_start, '%Y-%m-%d').date()
                        if isinstance(period_end, str):
                            period_end = datetime.strptime(period_end, '%Y-%m-%d').date()
                        # Check overlap
                        if check_in < period_end and check_out > period_start:
                            excluded_ids.add(listing.id)
                            break

        return queryset.exclude(id__in=excluded_ids)


class ListingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for listing CRUD operations.

    Permissions:
    - list/retrieve: Public (anyone can view active listings)
    - create: Authenticated users only
    - update/delete: Host (owner) only

    Endpoints:
    - GET /api/listings/ - List all active listings
    - POST /api/listings/ - Create new listing (authenticated)
    - GET /api/listings/{slug}/ - Get listing detail by slug
    - PUT/PATCH /api/listings/{slug}/ - Update listing (owner only)
    - DELETE /api/listings/{slug}/ - Delete listing (owner only)
    - GET /api/listings/{slug}/unavailable-dates/ - Get blocked dates
    - GET /api/listings/my_listings/ - Get user's listings
    """

    permission_classes = [IsHostOrReadOnly]
    filterset_class = ListingFilter
    search_fields = ['title', 'description', 'city', 'address']
    ordering_fields = ['price_per_night', 'created_at', 'max_guests']
    ordering = ['-created_at']
    lookup_field = 'slug'

    def get_queryset(self):
        queryset = Listing.objects.select_related('host').prefetch_related('images')

        # Show only active listings for public views
        if self.action == 'list' and not self.request.user.is_authenticated:
            queryset = queryset.filter(status=Listing.Status.ACTIVE)
        elif self.action == 'list' and self.request.user.is_authenticated:
            # Authenticated users see active listings + their own drafts
            from django.db.models import Q
            queryset = queryset.filter(
                Q(status=Listing.Status.ACTIVE) | Q(host=self.request.user)
            )

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return ListingListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ListingCreateUpdateSerializer
        return ListingDetailSerializer

    def perform_create(self, serializer):
        """Set the host to the current user when creating a listing."""
        serializer.save(host=self.request.user)

    @action(detail=True, methods=['get'], permission_classes=[permissions.AllowAny])
    def unavailable_dates(self, request, slug=None):
        """
        Get unavailable dates for a listing.

        Returns list of date ranges that cannot be booked.

        Response format:
        [
            {"start": "2026-03-01", "end": "2026-03-05", "type": "booking"},
            {"start": "2026-03-10", "end": "2026-03-12", "type": "blocked"}
        ]
        """
        listing = self.get_object()
        unavailable = BookingService.get_unavailable_dates(listing.id)
        return Response(unavailable)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_listings(self, request):
        """Get listings owned by the current user."""
        queryset = Listing.objects.filter(
            host=request.user
        ).prefetch_related('images').order_by('-created_at')

        serializer = ListingListSerializer(
            queryset,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class ListingImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing listing images.

    Permissions: Only the listing owner can manage images.
    """

    serializer_class = ListingImageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ListingImage.objects.filter(
            listing__host=self.request.user,
            listing_id=self.kwargs.get('listing_pk'),
        )

    def perform_create(self, serializer):
        listing = get_object_or_404(
            Listing,
            id=self.kwargs.get('listing_pk'),
            host=self.request.user,
        )
        serializer.save(listing=listing)


class AmenityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing amenities (read-only).

    Public endpoint for fetching available amenities.
    """

    queryset = ListingAmenity.objects.all()
    serializer_class = ListingAmenitySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for cities (read-only).

    Public endpoint for fetching available cities for dropdown.
    """

    queryset = City.objects.filter(is_active=True).order_by('order', 'name')
    serializer_class = CitySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None
    search_fields = ['name', 'province']
