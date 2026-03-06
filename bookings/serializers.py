"""Booking serializers for ZCA BnB with comprehensive validation."""

from datetime import date

from rest_framework import serializers

from listings.serializers import ListingListSerializer
from listings.models import Listing
from users.serializers import PublicUserSerializer, GuestIDSerializer
from users.models import GuestID
from .models import Booking, BlockedDate
from .services import BookingService


class BookingListSerializer(serializers.ModelSerializer):
    """Serializer for booking list view."""

    listing_title = serializers.CharField(source='listing.title', read_only=True)
    listing_city = serializers.CharField(source='listing.city', read_only=True)
    nights = serializers.IntegerField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'listing',
            'listing_title',
            'listing_city',
            'check_in',
            'check_out',
            'nights',
            'total_price',
            'currency',
            'status',
            'source',
            'created_at',
        ]


class BookingDetailSerializer(serializers.ModelSerializer):
    """Serializer for booking detail view."""

    listing = ListingListSerializer(read_only=True)
    guest = PublicUserSerializer(read_only=True)
    nights = serializers.IntegerField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'listing',
            'guest',
            'check_in',
            'check_out',
            'nights',
            'price_per_night',
            'cleaning_fee',
            'total_price',
            'currency',
            'num_guests',
            'guest_name',
            'guest_email',
            'guest_phone',
            'status',
            'source',
            'special_requests',
            'created_at',
            'confirmed_at',
        ]


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating bookings with comprehensive validation.

    Validates:
    - check_in < check_out
    - check_in is in the future
    - Dates don't conflict with existing bookings
    - Guest count within listing limits
    """

    listing_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Booking
        fields = [
            'listing_id',
            'check_in',
            'check_out',
            'num_guests',
            'guest_name',
            'guest_email',
            'guest_phone',
            'special_requests',
        ]

    def validate_listing_id(self, value):
        """Validate listing exists and is active."""
        try:
            listing = Listing.objects.get(id=value)
            if listing.status != Listing.Status.ACTIVE:
                raise serializers.ValidationError('This listing is not available for booking')
            return value
        except Listing.DoesNotExist:
            raise serializers.ValidationError('Listing not found')

    def validate_check_in(self, value):
        """Validate check_in is not in the past."""
        if value < date.today():
            raise serializers.ValidationError('Check-in date cannot be in the past')
        return value

    def validate(self, attrs):
        """Validate booking dates and availability."""
        check_in = attrs.get('check_in')
        check_out = attrs.get('check_out')
        listing_id = attrs.get('listing_id')
        num_guests = attrs.get('num_guests', 1)

        # Validate date order
        if check_in and check_out:
            if check_out <= check_in:
                raise serializers.ValidationError({
                    'check_out': 'Check-out date must be after check-in date'
                })

            # Validate against listing rules
            try:
                listing = Listing.objects.get(id=listing_id)

                nights = (check_out - check_in).days

                if nights < listing.minimum_nights:
                    raise serializers.ValidationError({
                        'check_out': f'Minimum stay is {listing.minimum_nights} night(s)'
                    })

                if nights > listing.maximum_nights:
                    raise serializers.ValidationError({
                        'check_out': f'Maximum stay is {listing.maximum_nights} nights'
                    })

                if num_guests > listing.max_guests:
                    raise serializers.ValidationError({
                        'num_guests': f'Maximum guests allowed is {listing.max_guests}'
                    })

                # Check availability
                is_available, error_msg = BookingService.check_availability(
                    listing_id, check_in, check_out
                )
                if not is_available:
                    raise serializers.ValidationError({
                        'check_in': error_msg or 'These dates are not available'
                    })

            except Listing.DoesNotExist:
                pass  # Already validated in validate_listing_id

        return attrs


class BookingStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating booking status."""

    status = serializers.ChoiceField(choices=[
        ('confirmed', 'Confirm'),
        ('cancelled', 'Cancel'),
    ])


class HostBookingSerializer(serializers.ModelSerializer):
    """Serializer for host's view of bookings."""

    guest = PublicUserSerializer(read_only=True)
    listing_title = serializers.CharField(source='listing.title', read_only=True)
    nights = serializers.IntegerField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'listing',
            'listing_title',
            'guest',
            'check_in',
            'check_out',
            'nights',
            'num_guests',
            'guest_name',
            'guest_email',
            'guest_phone',
            'total_price',
            'currency',
            'status',
            'source',
            'special_requests',
            'host_notes',
            'created_at',
            'confirmed_at',
        ]
        read_only_fields = [
            'id', 'listing', 'guest', 'check_in', 'check_out',
            'num_guests', 'total_price', 'source', 'created_at',
        ]


class BlockedDateSerializer(serializers.ModelSerializer):
    """Serializer for blocked dates."""

    class Meta:
        model = BlockedDate
        fields = ['id', 'listing', 'start_date', 'end_date', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        """Validate date range."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')

        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError({
                    'end_date': 'End date must be on or after start date'
                })

            if start_date < date.today():
                raise serializers.ValidationError({
                    'start_date': 'Start date cannot be in the past'
                })

        return attrs


class UnavailableDateSerializer(serializers.Serializer):
    """
    Serializer for unavailable date ranges.

    Used by GET /api/listings/{id}/unavailable-dates/
    """

    start = serializers.DateField()
    end = serializers.DateField()
    type = serializers.ChoiceField(choices=['booking', 'blocked'], read_only=True)


class CheckoutSerializer(serializers.Serializer):
    """
    Serializer for the checkout/payment flow.

    Validates booking data and optional guest ID selection.
    """

    listing_id = serializers.IntegerField()
    check_in = serializers.DateField()
    check_out = serializers.DateField()
    num_guests = serializers.IntegerField(min_value=1)
    guest_id = serializers.IntegerField(required=False, allow_null=True)
    new_guest_id_r2_key = serializers.CharField(required=False, allow_blank=True)
    new_guest_id_type = serializers.ChoiceField(
        choices=GuestID.IDType.choices,
        required=False,
    )
    message_to_host = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    special_requests = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate_listing_id(self, value):
        try:
            listing = Listing.objects.get(id=value)
            if listing.status != Listing.Status.ACTIVE:
                raise serializers.ValidationError('This listing is not available for booking')
            return value
        except Listing.DoesNotExist:
            raise serializers.ValidationError('Listing not found')

    def validate_check_in(self, value):
        if value < date.today():
            raise serializers.ValidationError('Check-in date cannot be in the past')
        return value

    def validate_guest_id(self, value):
        if value:
            user = self.context['request'].user
            if not GuestID.objects.filter(id=value, user=user).exists():
                raise serializers.ValidationError('Invalid guest ID')
        return value

    def validate(self, attrs):
        check_in = attrs.get('check_in')
        check_out = attrs.get('check_out')
        listing_id = attrs.get('listing_id')
        num_guests = attrs.get('num_guests', 1)

        # Validate date order
        if check_in and check_out:
            if check_out <= check_in:
                raise serializers.ValidationError({
                    'check_out': 'Check-out date must be after check-in date'
                })

            try:
                listing = Listing.objects.get(id=listing_id)
                nights = (check_out - check_in).days

                if nights < listing.minimum_nights:
                    raise serializers.ValidationError({
                        'check_out': f'Minimum stay is {listing.minimum_nights} night(s)'
                    })

                if nights > listing.maximum_nights:
                    raise serializers.ValidationError({
                        'check_out': f'Maximum stay is {listing.maximum_nights} nights'
                    })

                if num_guests > listing.max_guests:
                    raise serializers.ValidationError({
                        'num_guests': f'Maximum guests allowed is {listing.max_guests}'
                    })

                # Check availability
                is_available, error_msg = BookingService.check_availability(
                    listing_id, check_in, check_out
                )
                if not is_available:
                    raise serializers.ValidationError({
                        'check_in': error_msg or 'These dates are not available'
                    })

            except Listing.DoesNotExist:
                pass

        # Validate guest ID requirements
        guest_id = attrs.get('guest_id')
        new_guest_id_r2_key = attrs.get('new_guest_id_r2_key')
        new_guest_id_type = attrs.get('new_guest_id_type')

        if new_guest_id_r2_key and not new_guest_id_type:
            raise serializers.ValidationError({
                'new_guest_id_type': 'ID type is required when uploading a new ID'
            })

        return attrs


class CheckoutResponseSerializer(serializers.ModelSerializer):
    """Response serializer for checkout endpoint."""

    listing = ListingListSerializer(read_only=True)
    guest_id_document = GuestIDSerializer(read_only=True)
    nights = serializers.IntegerField(read_only=True)
    payment = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            'id',
            'listing',
            'check_in',
            'check_out',
            'nights',
            'num_guests',
            'price_per_night',
            'cleaning_fee',
            'total_price',
            'currency',
            'status',
            'message_to_host',
            'special_requests',
            'guest_id_document',
            'payment',
            'created_at',
        ]

    def get_payment(self, obj):
        from payments.serializers import PaymentSummarySerializer
        if hasattr(obj, 'payment'):
            return PaymentSummarySerializer(obj.payment).data
        return None
