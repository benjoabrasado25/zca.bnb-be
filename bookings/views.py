"""Booking views for ZCA BnB."""

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from listings.models import Listing
from users.models import GuestID
from users.services import check_id_exists
from .models import Booking, BlockedDate
from .serializers import (
    BookingListSerializer,
    BookingDetailSerializer,
    BookingCreateSerializer,
    BookingStatusUpdateSerializer,
    HostBookingSerializer,
    BlockedDateSerializer,
    CheckoutSerializer,
    CheckoutResponseSerializer,
)
from .services import (
    BookingService,
    DoubleBookingError,
    BookingValidationError,
)


class IsGuestOrHost(permissions.BasePermission):
    """Permission that allows guests and hosts appropriate access."""

    def has_object_permission(self, request, view, obj):
        # Guest can view their own bookings
        if obj.guest == request.user:
            return True
        # Host can view bookings for their listings
        if obj.listing.host == request.user:
            return True
        return False


class BookingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for booking operations.

    Guests can create bookings and view their own.
    Hosts can view and manage bookings for their listings.
    """

    permission_classes = [permissions.IsAuthenticated, IsGuestOrHost]

    def get_queryset(self):
        user = self.request.user

        # Get bookings where user is guest or host
        return Booking.objects.filter(
            guest=user
        ) | Booking.objects.filter(
            listing__host=user
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        elif self.action == 'list':
            return BookingListSerializer
        return BookingDetailSerializer

    def create(self, request, *args, **kwargs):
        """Create a new booking."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing_id = serializer.validated_data.pop('listing_id')
        listing = get_object_or_404(Listing, id=listing_id, status=Listing.Status.ACTIVE)

        try:
            booking = BookingService.create_booking(
                listing=listing,
                guest=request.user,
                auto_confirm=listing.is_instant_bookable,
                **serializer.validated_data
            )

            response_serializer = BookingDetailSerializer(booking, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DoubleBookingError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_409_CONFLICT
            )
        except BookingValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm a pending booking (host only)."""
        booking = self.get_object()

        # Only host can confirm
        if booking.listing.host != request.user:
            return Response(
                {'detail': 'Only the host can confirm bookings.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            booking = BookingService.confirm_booking(booking)
            serializer = BookingDetailSerializer(booking, context={'request': request})
            return Response(serializer.data)
        except (DoubleBookingError, BookingValidationError) as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a booking."""
        booking = self.get_object()

        # Both guest and host can cancel
        if booking.guest != request.user and booking.listing.host != request.user:
            return Response(
                {'detail': 'You do not have permission to cancel this booking.'},
                status=status.HTTP_403_FORBIDDEN
            )

        cancelled_by = 'guest' if booking.guest == request.user else 'host'

        try:
            booking = BookingService.cancel_booking(booking, cancelled_by=cancelled_by)
            serializer = BookingDetailSerializer(booking, context={'request': request})
            return Response(serializer.data)
        except BookingValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def my_bookings(self, request):
        """Get bookings where the current user is the guest."""
        bookings = Booking.objects.filter(guest=request.user).order_by('-created_at')
        serializer = BookingListSerializer(bookings, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def host_bookings(self, request):
        """Get bookings for listings owned by the current user."""
        bookings = Booking.objects.filter(
            listing__host=request.user
        ).order_by('-created_at')
        serializer = HostBookingSerializer(bookings, many=True)
        return Response(serializer.data)


class BlockedDateViewSet(viewsets.ModelViewSet):
    """ViewSet for managing blocked dates."""

    serializer_class = BlockedDateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BlockedDate.objects.filter(listing__host=self.request.user)

    def create(self, request, *args, **kwargs):
        """Create blocked dates for a listing."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get the listing from validated data (it's already a Listing object from PrimaryKeyRelatedField)
        listing = serializer.validated_data['listing']

        # Verify the user owns this listing
        if listing.host != request.user:
            return Response(
                {'detail': 'You do not have permission to block dates for this listing.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            blocked = BookingService.block_dates(
                listing=listing,
                start_date=serializer.validated_data['start_date'],
                end_date=serializer.validated_data['end_date'],
                reason=serializer.validated_data.get('reason', ''),
            )
            response_serializer = self.get_serializer(blocked)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        except BookingValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class CheckoutView(APIView):
    """
    Checkout endpoint for creating a booking with payment.

    POST /api/bookings/checkout/
    {
        "listing_id": 123,
        "check_in": "2026-03-15",
        "check_out": "2026-03-18",
        "num_guests": 2,
        "guest_id": 45,  // Existing GuestID id, or null
        "new_guest_id_r2_key": "guest-ids/123/uuid.jpg",  // If uploading new
        "new_guest_id_type": "national_id",
        "message_to_host": "Hi, we're excited to visit!",
        "special_requests": "Late check-in please"
    }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Get the listing
        listing = get_object_or_404(Listing, id=data['listing_id'])

        # Handle guest ID
        guest_id_document = None

        if data.get('guest_id'):
            # Use existing guest ID
            guest_id_document = get_object_or_404(
                GuestID,
                id=data['guest_id'],
                user=request.user
            )
        elif data.get('new_guest_id_r2_key'):
            # Create new guest ID from uploaded file
            r2_key = data['new_guest_id_r2_key']

            # Verify the key belongs to this user
            expected_prefix = f"guest-ids/{request.user.id}/"
            if not r2_key.startswith(expected_prefix):
                return Response(
                    {'detail': 'Invalid guest ID upload'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Verify file exists
            if not check_id_exists(r2_key):
                return Response(
                    {'detail': 'Guest ID upload not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create GuestID record
            guest_id_document = GuestID.objects.create(
                user=request.user,
                r2_key=r2_key,
                id_type=data['new_guest_id_type'],
                is_primary=True,
            )

        # Create the booking
        try:
            booking = BookingService.create_booking(
                listing=listing,
                guest=request.user,
                check_in=data['check_in'],
                check_out=data['check_out'],
                num_guests=data['num_guests'],
                special_requests=data.get('special_requests', ''),
                auto_confirm=False,  # Wait for payment
            )

            # Add message to host and guest ID
            booking.message_to_host = data.get('message_to_host', '')
            booking.guest_id_document = guest_id_document
            booking.save()

        except DoubleBookingError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_409_CONFLICT
            )
        except BookingValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create Xendit payment invoice
        from payments.services import create_invoice, XenditError

        frontend_url = settings.FRONTEND_URL
        success_url = f"{frontend_url}/booking-confirmation?booking_id={booking.id}"
        failure_url = f"{frontend_url}/checkout/{listing.slug}?payment_failed=true"

        try:
            payment = create_invoice(
                booking=booking,
                success_redirect_url=success_url,
                failure_redirect_url=failure_url,
            )
        except XenditError as e:
            # Delete the booking if payment creation fails
            booking.delete()
            return Response(
                {'detail': f'Failed to create payment: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Return the booking with payment info
        response_serializer = CheckoutResponseSerializer(
            booking,
            context={'request': request}
        )

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
