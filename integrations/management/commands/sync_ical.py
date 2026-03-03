"""
Management command to synchronize all iCal feeds.

Usage:
    python manage.py sync_ical
    python manage.py sync_ical --listing-id=123
    python manage.py sync_ical --verbose
    python manage.py sync_ical --all  # Include paused syncs

This command should be run periodically via cron or Celery beat.

Recommended cron schedule (every hour):
    0 * * * * cd /path/to/project && python manage.py sync_ical >> /var/log/ical_sync.log 2>&1
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from integrations.models import IcalSync, IcalSyncLog
from integrations.ical_service import IcalImportService


class Command(BaseCommand):
    help = 'Synchronize bookings from external iCal feeds (Airbnb, Booking.com, etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--listing-id',
            type=int,
            help='Sync only for a specific listing ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Include paused syncs (normally only active syncs are processed)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each sync',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Fetch and parse without saving (for testing)',
        )

    def handle(self, *args, **options):
        listing_id = options.get('listing_id')
        include_paused = options.get('all', False)
        verbose = options.get('verbose', False)
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.NOTICE(
            f'Starting iCal sync at {timezone.now().isoformat()}'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))

        # Build queryset
        queryset = IcalSync.objects.select_related('listing')

        if listing_id:
            queryset = queryset.filter(listing_id=listing_id)

        if not include_paused:
            queryset = queryset.filter(status=IcalSync.SyncStatus.ACTIVE)

        syncs = queryset.all()

        if not syncs:
            self.stdout.write(self.style.WARNING('No iCal syncs found to process'))
            return

        self.stdout.write(f'Processing {syncs.count()} iCal sync(s)...\n')

        total_created = 0
        total_updated = 0
        total_conflicts = 0
        total_errors = 0

        for ical_sync in syncs:
            if verbose:
                self.stdout.write(f'\n{"="*50}')
                self.stdout.write(f'Listing: {ical_sync.listing.title} (ID: {ical_sync.listing.id})')
                self.stdout.write(f'Platform: {ical_sync.get_platform_display()}')
                self.stdout.write(f'URL: {ical_sync.airbnb_import_url[:60]}...')
                self.stdout.write(f'Last synced: {ical_sync.last_synced_at or "Never"}')

            try:
                if dry_run:
                    # Fetch and parse only
                    content, fetch_error = IcalImportService.fetch_ical(ical_sync.airbnb_import_url)
                    if fetch_error:
                        self.stdout.write(self.style.ERROR(f'  Fetch error: {fetch_error}'))
                        total_errors += 1
                        continue

                    events, parse_error = IcalImportService.parse_ical(content)
                    if parse_error:
                        self.stdout.write(self.style.ERROR(f'  Parse error: {parse_error}'))
                        total_errors += 1
                        continue

                    self.stdout.write(self.style.SUCCESS(f'  Would process {len(events)} events'))
                    continue

                # Perform actual sync
                created, updated, skipped, conflicts, error = IcalImportService.sync_ical(ical_sync)

                # Determine log status
                if error:
                    log_status = IcalSyncLog.Status.FAILED
                elif conflicts > 0 and (created > 0 or updated > 0):
                    log_status = IcalSyncLog.Status.PARTIAL
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
                    total_errors += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  Error: {error}'))
                else:
                    ical_sync.last_error = ''
                    ical_sync.status = IcalSync.SyncStatus.ACTIVE
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(
                            f'  Success: {created} created, {updated} updated, '
                            f'{skipped} skipped, {conflicts} conflicts'
                        ))

                ical_sync.save(update_fields=[
                    'last_synced_at', 'sync_count', 'last_error', 'status', 'updated_at'
                ])

                total_created += created
                total_updated += updated
                total_conflicts += conflicts

            except Exception as e:
                total_errors += 1
                self.stdout.write(self.style.ERROR(
                    f'  Unexpected error for {ical_sync.listing.title}: {e}'
                ))

                # Log the error
                IcalSyncLog.objects.create(
                    ical_sync=ical_sync,
                    status=IcalSyncLog.Status.FAILED,
                    error_message=str(e),
                )

                ical_sync.last_synced_at = timezone.now()
                ical_sync.last_error = str(e)
                ical_sync.status = IcalSync.SyncStatus.ERROR
                ical_sync.save(update_fields=[
                    'last_synced_at', 'last_error', 'status', 'updated_at'
                ])

        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(f'Sync completed at {timezone.now().isoformat()}'))
        self.stdout.write(f'  Total syncs processed: {syncs.count()}')
        self.stdout.write(f'  Bookings created: {total_created}')
        self.stdout.write(f'  Bookings updated: {total_updated}')
        self.stdout.write(f'  Conflicts skipped: {total_conflicts}')

        if total_errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {total_errors}'))
        else:
            self.stdout.write(self.style.SUCCESS('  Errors: 0'))
