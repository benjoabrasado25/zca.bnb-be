"""
Booking services with database-level protection against double bookings.

Uses:
1. PostgreSQL EXCLUDE constraint (primary protection)
2. transaction.atomic() + select_for_update() for race condition prevention
3. Application-level validation for better error messages

This works for ALL booking sources:
- Manual bookings via frontend
- iCal imported bookings (Airbnb, Booking.com, etc.)
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils import timezone

from listings.models import Listing
from .models import Booking, BlockedDate

logger = logging.getLogger(__name__)


class DoubleBookingError(Exception):
    """Raised when a booking would create a date conflict."""
    pass


class BookingValidationError(Exception):
    """Raised when booking data is invalid."""
    pass


class BookingService:
    """
    Service for managing bookings with comprehensive double-booking prevention.

    Protection layers:
    1. Application validation (check_availability) - gives user-friendly errors
    2. PostgreSQL EXCLUDE constraint - absolute guarantee at DB level
    3. transaction.atomic() + select_for_update() - prevents race conditions
    """

    @staticmethod
    def get_unavailable_dates(listing_id: int) -> List[Dict[str, str]]:
        """
        Get all unavailable date ranges for a listing.

        Returns a list of date ranges that are blocked or booked.
        Format: [{"start": "2026-03-01", "end": "2026-03-05", "type": "booking"}, ...]

        Used by:
        - GET /api/listings/{id}/unavailable-dates/
        - Frontend date picker to disable unavailable dates
        """
        unavailable = []

        # Get confirmed and pending bookings (not cancelled)
        bookings = Booking.objects.filter(
            listing_id=listing_id,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
            check_out__gte=date.today(),
        ).values('check_in', 'check_out', 'source')

        for booking in bookings:
            unavailable.append({
                'start': booking['check_in'].isoformat(),
                'end': booking['check_out'].isoformat(),
                'type': 'booking',
            })

        # Get blocked dates (host-defined unavailable periods)
        blocked = BlockedDate.objects.filter(
            listing_id=listing_id,
            end_date__gte=date.today(),
        ).values('start_date', 'end_date')

        for block in blocked:
            unavailable.append({
                'start': block['start_date'].isoformat(),
                'end': block['end_date'].isoformat(),
                'type': 'blocked',
            })

        # Sort by start date for consistent frontend display
        return sorted(unavailable, key=lambda x: x['start'])

    @staticmethod
    def check_availability(
        listing_id: int,
        check_in: date,
        check_out: date,
        exclude_booking_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if dates are available for booking.

        Returns:
            Tuple of (is_available, error_message)

        Uses select_for_update to prevent race conditions during check.
        """
        with transaction.atomic():
            # Lock the listing row to prevent concurrent modifications
            try:
                listing = Listing.objects.select_for_update(nowait=True).get(id=listing_id)
            except Listing.DoesNotExist:
                return False, "Listing not found"

            # Check for conflicting bookings
            # Overlapping logic: new booking overlaps if:
            # new_check_in < existing_check_out AND new_check_out > existing_check_in
            conflicting_bookings = Booking.objects.filter(
                listing_id=listing_id,
                status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
                check_in__lt=check_out,
                check_out__gt=check_in,
            )

            if exclude_booking_id:
                conflicting_bookings = conflicting_bookings.exclude(id=exclude_booking_id)

            conflict = conflicting_bookings.first()
            if conflict:
                return False, f"Dates conflict with existing booking ({conflict.check_in} - {conflict.check_out})"

            # Check for blocked dates
            conflicting_blocks = BlockedDate.objects.filter(
                listing_id=listing_id,
                start_date__lt=check_out,
                end_date__gt=check_in,
            ).first()

            if conflicting_blocks:
                return False, f"Dates are blocked by host ({conflicting_blocks.start_date} - {conflicting_blocks.end_date})"

            return True, None

    @classmethod
    def validate_booking_dates(cls, listing: Listing, check_in: date, check_out: date, num_guests: int = 1):
        """
        Validate booking dates against listing rules.

        Raises BookingValidationError with specific error messages.
        """
        # Check date order
        if check_out <= check_in:
            raise BookingValidationError('Check-out date must be after check-in date')

        # Check if check_in is in the past
        today = date.today()
        if check_in < today:
            raise BookingValidationError('Check-in date cannot be in the past')

        # Calculate nights
        nights = (check_out - check_in).days

        # Check minimum nights
        if nights < listing.minimum_nights:
            raise BookingValidationError(
                f'Minimum stay is {listing.minimum_nights} night{"s" if listing.minimum_nights > 1 else ""}'
            )

        # Check maximum nights
        if nights > listing.maximum_nights:
            raise BookingValidationError(
                f'Maximum stay is {listing.maximum_nights} nights'
            )

        # Check guest count
        if num_guests > listing.max_guests:
            raise BookingValidationError(
                f'Maximum guests allowed is {listing.max_guests}'
            )

        # Check if listing is active
        if listing.status != Listing.Status.ACTIVE:
            raise BookingValidationError('This listing is not available for booking')

    @classmethod
    def create_booking(
        cls,
        listing: Listing,
        check_in: date,
        check_out: date,
        guest=None,
        num_guests: int = 1,
        guest_name: str = '',
        guest_email: str = '',
        guest_phone: str = '',
        special_requests: str = '',
        source: str = Booking.Source.MANUAL,
        external_uid: str = '',
        auto_confirm: bool = False,
    ) -> Booking:
        """
        Create a new booking with comprehensive double-booking prevention.

        Protection layers:
        1. Validates dates against listing rules
        2. Checks availability with select_for_update (race condition prevention)
        3. PostgreSQL EXCLUDE constraint (database-level guarantee)

        Works for both manual bookings and iCal imports.
        """
        # Step 1: Validate booking dates
        cls.validate_booking_dates(listing, check_in, check_out, num_guests)

        # Calculate pricing
        nights = (check_out - check_in).days
        price_per_night = listing.price_per_night
        cleaning_fee = listing.cleaning_fee
        total_price = (price_per_night * nights) + cleaning_fee

        try:
            with transaction.atomic():
                # Step 2: Lock listing and check availability
                locked_listing = Listing.objects.select_for_update().get(id=listing.id)

                is_available, error_msg = cls.check_availability(listing.id, check_in, check_out)
                if not is_available:
                    raise DoubleBookingError(error_msg or 'These dates are no longer available')

                # Determine initial status
                status = Booking.Status.CONFIRMED if auto_confirm else Booking.Status.PENDING
                confirmed_at = timezone.now() if auto_confirm else None

                # Step 3: Create the booking (PostgreSQL constraint provides final guarantee)
                booking = Booking.objects.create(
                    listing=locked_listing,
                    guest=guest,
                    check_in=check_in,
                    check_out=check_out,
                    price_per_night=price_per_night,
                    cleaning_fee=cleaning_fee,
                    total_price=total_price,
                    currency=listing.currency,
                    num_guests=num_guests,
                    guest_name=guest_name or (guest.get_full_name() if guest else ''),
                    guest_email=guest_email or (guest.email if guest else ''),
                    guest_phone=guest_phone,
                    status=status,
                    source=source,
                    external_uid=external_uid,
                    special_requests=special_requests,
                    confirmed_at=confirmed_at,
                )

                logger.info(
                    f"Booking created: ID={booking.id}, listing={listing.id}, "
                    f"dates={check_in} to {check_out}, source={source}, status={status}"
                )

                return booking

        except IntegrityError as e:
            # PostgreSQL constraint violation - double booking prevented at DB level
            logger.warning(
                f"Double booking prevented by DB constraint: listing={listing.id}, "
                f"dates={check_in} to {check_out}, source={source}, error={e}"
            )
            raise DoubleBookingError(
                'These dates are no longer available. '
                'Another booking was made for the same period.'
            )

    @classmethod
    def confirm_booking(cls, booking: Booking) -> Booking:
        """Confirm a pending booking."""
        if booking.status != Booking.Status.PENDING:
            raise BookingValidationError(
                f'Cannot confirm booking with status "{booking.get_status_display()}"'
            )

        with transaction.atomic():
            # Re-verify availability (another booking might have been confirmed)
            is_available, error_msg = cls.check_availability(
                booking.listing_id,
                booking.check_in,
                booking.check_out,
                exclude_booking_id=booking.id,
            )

            if not is_available:
                raise DoubleBookingError(f'Cannot confirm: {error_msg}')

            booking.status = Booking.Status.CONFIRMED
            booking.confirmed_at = timezone.now()
            booking.save(update_fields=['status', 'confirmed_at', 'updated_at'])

        logger.info(f"Booking confirmed: ID={booking.id}")
        return booking

    @classmethod
    def cancel_booking(
        cls,
        booking: Booking,
        cancelled_by: str = 'system',
    ) -> Booking:
        """Cancel a booking and free up the dates."""
        if booking.status == Booking.Status.CANCELLED:
            raise BookingValidationError('Booking is already cancelled')

        booking.status = Booking.Status.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.host_notes = f"{booking.host_notes}\nCancelled by {cancelled_by} at {timezone.now().isoformat()}"
        booking.save(update_fields=['status', 'cancelled_at', 'host_notes', 'updated_at'])

        logger.info(f"Booking cancelled: ID={booking.id}, by={cancelled_by}")
        return booking

    @classmethod
    def create_or_update_ical_booking(
        cls,
        listing: Listing,
        external_uid: str,
        check_in: date,
        check_out: date,
        summary: str = '',
        source: str = Booking.Source.AIRBNB_ICAL,
    ) -> Tuple[Optional[Booking], str]:
        """
        Create or update a booking from an iCal source.

        Uses external_uid for deduplication.

        Returns:
            Tuple of (booking, status) where status is one of:
            - 'created': New booking was created
            - 'updated': Existing booking was updated
            - 'skipped': No changes needed
            - 'conflict': Dates conflict with existing booking
            - 'error': An error occurred
        """
        # Validate dates
        if check_out <= check_in:
            logger.warning(f"iCal import skipped: invalid dates {check_in} to {check_out}")
            return None, 'error'

        if check_out < date.today():
            logger.debug(f"iCal import skipped: past booking {check_in} to {check_out}")
            return None, 'skipped'

        with transaction.atomic():
            # Check if booking already exists by external_uid
            existing = Booking.objects.filter(
                listing=listing,
                external_uid=external_uid,
            ).select_for_update().first()

            if existing:
                # Update existing booking if dates changed
                if existing.check_in != check_in or existing.check_out != check_out:
                    # Check if new dates conflict
                    is_available, _ = cls.check_availability(
                        listing.id, check_in, check_out, exclude_booking_id=existing.id
                    )

                    if not is_available:
                        logger.warning(
                            f"iCal update conflict: UID={external_uid}, "
                            f"new dates {check_in} to {check_out} conflict"
                        )
                        return existing, 'conflict'

                    existing.check_in = check_in
                    existing.check_out = check_out
                    existing.save(update_fields=['check_in', 'check_out', 'updated_at'])

                    logger.info(
                        f"iCal booking updated: ID={existing.id}, UID={external_uid}, "
                        f"dates={check_in} to {check_out}"
                    )
                    return existing, 'updated'

                return existing, 'skipped'

            # Check availability before creating
            is_available, error_msg = cls.check_availability(listing.id, check_in, check_out)

            if not is_available:
                logger.warning(
                    f"iCal import conflict: UID={external_uid}, "
                    f"dates {check_in} to {check_out}, reason: {error_msg}"
                )
                return None, 'conflict'

            # Create new booking
            try:
                booking = cls.create_booking(
                    listing=listing,
                    check_in=check_in,
                    check_out=check_out,
                    guest_name=summary or 'External Guest',
                    source=source,
                    external_uid=external_uid,
                    auto_confirm=True,  # iCal imports are auto-confirmed
                )
                return booking, 'created'

            except DoubleBookingError as e:
                logger.warning(f"iCal import double booking: UID={external_uid}, error={e}")
                return None, 'conflict'
            except BookingValidationError as e:
                logger.warning(f"iCal import validation error: UID={external_uid}, error={e}")
                return None, 'error'

    @staticmethod
    def get_bookings_for_listing(
        listing_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status: Optional[str] = None,
    ):
        """Get bookings for a listing with optional filters."""
        queryset = Booking.objects.filter(listing_id=listing_id)

        if start_date:
            queryset = queryset.filter(check_out__gte=start_date)
        if end_date:
            queryset = queryset.filter(check_in__lte=end_date)
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by('check_in')

    @classmethod
    def block_dates(
        cls,
        listing: Listing,
        start_date: date,
        end_date: date,
        reason: str = '',
    ) -> BlockedDate:
        """
        Block dates for a listing (host-defined unavailable periods).

        Validates that no existing bookings conflict with the blocked period.
        """
        if end_date < start_date:
            raise BookingValidationError('End date must be on or after start date')

        try:
            with transaction.atomic():
                # Check for existing bookings in this range
                conflicting = Booking.objects.filter(
                    listing=listing,
                    status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
                    check_in__lt=end_date,
                    check_out__gt=start_date,
                ).first()

                if conflicting:
                    raise BookingValidationError(
                        f'Cannot block dates: existing booking from '
                        f'{conflicting.check_in} to {conflicting.check_out}'
                    )

                blocked = BlockedDate.objects.create(
                    listing=listing,
                    start_date=start_date,
                    end_date=end_date,
                    reason=reason,
                )

                logger.info(
                    f"Dates blocked: listing={listing.id}, "
                    f"dates={start_date} to {end_date}"
                )
                return blocked

        except IntegrityError:
            raise BookingValidationError(
                'These dates overlap with existing blocked dates'
            )
