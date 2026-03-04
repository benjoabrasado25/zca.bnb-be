"""
iCal service for import and export operations.

Implements RFC 5545 compliant iCal generation and parsing.
Compatible with Airbnb, Booking.com, and VRBO calendar sync.

Key features:
- RFC 5545 compliant .ics export
- Conflict-safe iCal import (skips conflicting bookings)
- Deduplication via external_uid
- Comprehensive logging
"""

import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple

import requests
from django.utils import timezone
from icalendar import Calendar, Event, vText
from dateutil import parser as date_parser

from bookings.models import Booking
from bookings.services import BookingService
from listings.models import Listing
from .models import IcalSync, IcalSyncLog

logger = logging.getLogger(__name__)


class IcalExportService:
    """
    Service for exporting bookings as iCal feed.

    Generates RFC 5545 compliant .ics content that can be imported
    into Airbnb, Booking.com, VRBO, Google Calendar, etc.
    """

    @staticmethod
    def generate_calendar(listing: Listing) -> str:
        """
        Generate an iCal calendar for a listing.

        Returns RFC 5545 compliant .ics content with:
        - Confirmed and pending bookings as VEVENT
        - Blocked dates as VEVENT
        - Proper UID format for deduplication
        - DTSTAMP, DTSTART, DTEND in correct format
        """
        cal = Calendar()

        # Calendar metadata (required by RFC 5545)
        cal.add('prodid', '-//ZCA BnB//Booking Calendar//EN')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('method', 'PUBLISH')
        cal.add('x-wr-calname', f'{listing.title} - ZCA BnB')
        cal.add('x-wr-timezone', 'Asia/Manila')

        # Get confirmed and pending bookings (include recent past for sync)
        bookings = Booking.objects.filter(
            listing=listing,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
            check_out__gte=date.today() - timedelta(days=30),
        ).order_by('check_in')

        for booking in bookings:
            event = Event()

            # Generate unique UID (required for deduplication by external systems)
            uid = f'booking-{booking.id}@zcabnb.com'
            event.add('uid', uid)

            # All-day events for bookings (DATE type, not DATETIME)
            event.add('dtstart', booking.check_in)
            event.add('dtend', booking.check_out)

            # Summary - privacy-conscious (Airbnb shows "Reserved")
            summary = 'Reserved'
            if booking.guest_name:
                summary = f'Reserved - {booking.guest_name}'
            event.add('summary', summary)

            # Description with booking details
            description_lines = [
                f'Booking #{booking.id}',
                f'Check-in: {booking.check_in}',
                f'Check-out: {booking.check_out}',
                f'Guests: {booking.num_guests}',
                f'Status: {booking.get_status_display()}',
            ]
            event.add('description', '\n'.join(description_lines))

            # Location
            event.add('location', vText(f'{listing.address}, {listing.city}'))

            # Timestamps (required by RFC 5545)
            event.add('dtstamp', timezone.now())
            event.add('created', booking.created_at)
            event.add('last-modified', booking.updated_at)

            # Status mapping
            if booking.status == Booking.Status.CONFIRMED:
                event.add('status', 'CONFIRMED')
            elif booking.status == Booking.Status.PENDING:
                event.add('status', 'TENTATIVE')

            # Show as busy (opaque)
            event.add('transp', 'OPAQUE')

            cal.add_component(event)

        # Add blocked dates as events
        for blocked in listing.blocked_dates.filter(end_date__gte=date.today()):
            event = Event()
            event.add('uid', f'blocked-{blocked.id}@zcabnb.com')
            event.add('dtstart', blocked.start_date)
            event.add('dtend', blocked.end_date + timedelta(days=1))  # End date is exclusive
            event.add('summary', 'Not Available')
            event.add('description', blocked.reason or 'Blocked by host')
            event.add('status', 'CONFIRMED')
            event.add('transp', 'OPAQUE')
            event.add('dtstamp', timezone.now())
            cal.add_component(event)

        return cal.to_ical().decode('utf-8')


class IcalImportService:
    """
    Service for importing bookings from external iCal feeds.

    Handles:
    - Fetching iCal from URLs (Airbnb, Booking.com, VRBO)
    - Parsing VEVENT components
    - Conflict detection (skips conflicting bookings)
    - Deduplication via UID
    - Comprehensive logging
    """

    TIMEOUT = 30  # seconds
    USER_AGENT = 'ZCA-BnB-Calendar-Sync/1.0'

    @classmethod
    def fetch_ical(cls, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch iCal content from a URL.

        Returns:
            Tuple of (content, error_message)
        """
        try:
            response = requests.get(
                url,
                timeout=cls.TIMEOUT,
                headers={
                    'User-Agent': cls.USER_AGENT,
                    'Accept': 'text/calendar, application/ics, */*',
                },
                allow_redirects=True,
            )
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')
            if 'text/calendar' not in content_type and 'ics' not in content_type:
                logger.warning(f"Unexpected content-type from {url}: {content_type}")

            return response.text, None

        except requests.Timeout:
            error = f"Timeout fetching iCal from {url}"
            logger.error(error)
            return None, error
        except requests.RequestException as e:
            error = f"Failed to fetch iCal: {str(e)}"
            logger.error(f"{error} - URL: {url}")
            return None, error

    @classmethod
    def parse_ical(cls, ical_content: str) -> Tuple[List[dict], Optional[str]]:
        """
        Parse iCal content and extract events.

        Returns:
            Tuple of (events_list, error_message)

        Each event dict contains:
        - uid: Unique identifier
        - summary: Event title
        - start: Start date
        - end: End date
        - status: Event status (CONFIRMED, TENTATIVE, CANCELLED)
        """
        events = []

        try:
            cal = Calendar.from_ical(ical_content)

            for component in cal.walk():
                if component.name == 'VEVENT':
                    event = cls._parse_vevent(component)
                    if event:
                        events.append(event)

            logger.info(f"Parsed {len(events)} events from iCal feed")
            return events, None

        except Exception as e:
            error = f"Failed to parse iCal content: {str(e)}"
            logger.error(error)
            return [], error

    @staticmethod
    def _parse_vevent(component) -> Optional[dict]:
        """Parse a VEVENT component into a dictionary."""
        try:
            # Get UID (required for deduplication)
            uid = str(component.get('uid', ''))
            if not uid:
                logger.debug("Skipping VEVENT without UID")
                return None

            # Get dates
            dtstart = component.get('dtstart')
            dtend = component.get('dtend')

            if not dtstart:
                logger.debug(f"Skipping VEVENT {uid}: no start date")
                return None

            # Convert to date objects (handle both DATE and DATETIME)
            start_date = dtstart.dt
            if isinstance(start_date, datetime):
                start_date = start_date.date()

            if dtend:
                end_date = dtend.dt
                if isinstance(end_date, datetime):
                    end_date = end_date.date()
            else:
                # If no end date, assume 1 night stay
                end_date = start_date + timedelta(days=1)

            # Validate dates
            if end_date <= start_date:
                logger.debug(f"Skipping VEVENT {uid}: invalid date range")
                return None

            # Get summary
            summary = str(component.get('summary', 'Reserved'))

            # Get status (CONFIRMED, TENTATIVE, CANCELLED)
            status = str(component.get('status', 'CONFIRMED')).upper()

            return {
                'uid': uid,
                'summary': summary,
                'start': start_date,
                'end': end_date,
                'status': status,
            }

        except Exception as e:
            logger.warning(f"Failed to parse VEVENT: {e}")
            return None

    @classmethod
    def sync_ical(cls, ical_sync: IcalSync) -> Tuple[int, int, int, int, str]:
        """
        Synchronize bookings from an iCal feed.

        Handles:
        - Fetching and parsing iCal
        - Deduplication via UID
        - Conflict detection (skips conflicting events)
        - Updates last_synced_at

        Returns:
            Tuple of (created, updated, skipped, conflicts, error_message)
        """
        created = 0
        updated = 0
        skipped = 0
        conflicts = 0
        error_message = ''

        logger.info(
            f"Starting iCal sync: listing={ical_sync.listing.id}, "
            f"platform={ical_sync.platform}"
        )

        # Fetch iCal content
        content, fetch_error = cls.fetch_ical(ical_sync.airbnb_import_url)
        if fetch_error:
            return created, updated, skipped, conflicts, fetch_error

        # Parse events
        events, parse_error = cls.parse_ical(content)
        if parse_error:
            return created, updated, skipped, conflicts, parse_error

        if not events:
            logger.info("No events found in iCal feed")
            return created, updated, skipped, conflicts, ''

        # Determine booking source based on platform
        source_map = {
            IcalSync.Platform.AIRBNB: Booking.Source.AIRBNB_ICAL,
            IcalSync.Platform.BOOKING_COM: Booking.Source.BOOKING_COM_ICAL,
            IcalSync.Platform.VRBO: Booking.Source.OTHER_ICAL,
            IcalSync.Platform.OTHER: Booking.Source.OTHER_ICAL,
        }
        source = source_map.get(ical_sync.platform, Booking.Source.OTHER_ICAL)

        # Process each event
        for event in events:
            # Skip cancelled events
            if event['status'] == 'CANCELLED':
                skipped += 1
                continue

            # Skip past events (optimization)
            if event['end'] < date.today():
                skipped += 1
                continue

            # Create or update booking with conflict handling
            booking, status = BookingService.create_or_update_ical_booking(
                listing=ical_sync.listing,
                external_uid=event['uid'],
                check_in=event['start'],
                check_out=event['end'],
                summary=event['summary'],
                source=source,
            )

            if status == 'created':
                created += 1
            elif status == 'updated':
                updated += 1
            elif status == 'conflict':
                conflicts += 1
                logger.warning(
                    f"iCal conflict: UID={event['uid']}, "
                    f"dates={event['start']} to {event['end']}"
                )
            else:  # skipped or error
                skipped += 1

        logger.info(
            f"iCal sync completed: listing={ical_sync.listing.id}, "
            f"created={created}, updated={updated}, skipped={skipped}, conflicts={conflicts}"
        )

        # Also update the listing's booked_dates JSON field directly (like WordPress)
        # This ensures availability data is always up to date
        try:
            all_booked = []
            for event in events:
                if event['status'] == 'CANCELLED':
                    continue
                if event['end'] < date.today():
                    continue
                all_booked.append({
                    'start': event['start'].isoformat(),
                    'end': event['end'].isoformat(),
                    'summary': event.get('summary', 'Reserved'),
                })

            # Update listing's booked_dates field
            listing = ical_sync.listing
            listing.booked_dates = all_booked
            listing.ical_last_synced = timezone.now()
            listing.save(update_fields=['booked_dates', 'ical_last_synced', 'updated_at'])
            logger.info(f"Updated listing.booked_dates with {len(all_booked)} date ranges")
        except Exception as e:
            logger.warning(f"Failed to update listing.booked_dates: {e}")

        return created, updated, skipped, conflicts, error_message

    @classmethod
    def sync_all(cls) -> dict:
        """
        Synchronize all active iCal syncs.

        Returns a summary dictionary.
        """
        syncs = IcalSync.objects.filter(
            status=IcalSync.SyncStatus.ACTIVE
        ).select_related('listing')

        results = {
            'total': syncs.count(),
            'success': 0,
            'failed': 0,
            'events_created': 0,
            'events_updated': 0,
            'conflicts': 0,
        }

        logger.info(f"Starting bulk iCal sync: {results['total']} syncs")

        for ical_sync in syncs:
            created, updated, skipped, conflicts, error = cls.sync_ical(ical_sync)

            # Determine log status
            if error:
                log_status = IcalSyncLog.Status.FAILED
            elif conflicts > 0 and (created > 0 or updated > 0):
                log_status = IcalSyncLog.Status.PARTIAL
            elif created > 0 or updated > 0:
                log_status = IcalSyncLog.Status.SUCCESS
            else:
                log_status = IcalSyncLog.Status.SUCCESS

            # Create log entry
            IcalSyncLog.objects.create(
                ical_sync=ical_sync,
                status=log_status,
                events_found=created + updated + skipped + conflicts,
                events_created=created,
                events_updated=updated,
                events_skipped=skipped + conflicts,
                error_message=error,
            )

            # Update sync record
            ical_sync.last_synced_at = timezone.now()
            ical_sync.sync_count += 1

            if error:
                ical_sync.last_error = error
                ical_sync.status = IcalSync.SyncStatus.ERROR
                results['failed'] += 1
            else:
                ical_sync.last_error = ''
                ical_sync.status = IcalSync.SyncStatus.ACTIVE
                results['success'] += 1

            ical_sync.save(update_fields=[
                'last_synced_at', 'sync_count', 'last_error', 'status', 'updated_at'
            ])

            results['events_created'] += created
            results['events_updated'] += updated
            results['conflicts'] += conflicts

        logger.info(
            f"Bulk iCal sync completed: "
            f"{results['success']}/{results['total']} successful, "
            f"{results['events_created']} created, {results['events_updated']} updated, "
            f"{results['conflicts']} conflicts"
        )

        return results


class IcalSyncService:
    """
    High-level service for iCal sync operations.
    Provides a simple interface for manual sync from admin.
    """

    def sync(self, ical_sync: IcalSync) -> Tuple[bool, str]:
        """
        Synchronize a single iCal feed.

        Returns:
            Tuple of (success, message)
        """
        logger.info(f"IcalSyncService.sync called for listing={ical_sync.listing_id}, url={ical_sync.airbnb_import_url}")
        created, updated, skipped, conflicts, error = IcalImportService.sync_ical(ical_sync)
        logger.info(f"IcalSyncService.sync result: created={created}, updated={updated}, skipped={skipped}, conflicts={conflicts}, error={error}")

        # Determine log status
        if error:
            log_status = IcalSyncLog.Status.FAILED
        elif conflicts > 0 and (created > 0 or updated > 0):
            log_status = IcalSyncLog.Status.PARTIAL
        elif created > 0 or updated > 0:
            log_status = IcalSyncLog.Status.SUCCESS
        else:
            log_status = IcalSyncLog.Status.SUCCESS

        # Create log entry
        IcalSyncLog.objects.create(
            ical_sync=ical_sync,
            status=log_status,
            events_found=created + updated + skipped + conflicts,
            events_created=created,
            events_updated=updated,
            events_skipped=skipped + conflicts,
            error_message=error,
        )

        # Update sync record
        ical_sync.last_synced_at = timezone.now()
        ical_sync.sync_count += 1

        if error:
            ical_sync.last_error = error
            ical_sync.status = IcalSync.SyncStatus.ERROR
            ical_sync.save(update_fields=[
                'last_synced_at', 'sync_count', 'last_error', 'status', 'updated_at'
            ])
            return False, error
        else:
            ical_sync.last_error = ''
            ical_sync.status = IcalSync.SyncStatus.ACTIVE
            ical_sync.save(update_fields=[
                'last_synced_at', 'sync_count', 'last_error', 'status', 'updated_at'
            ])

            message = f"Created {created}, updated {updated}"
            if conflicts > 0:
                message += f", {conflicts} conflicts skipped"
            return True, message
