"""
Celery tasks for iCal synchronization.

These tasks are scheduled via django-celery-beat.
"""

import logging

from celery import shared_task
from django.conf import settings

from .ical_service import IcalImportService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def sync_all_ical_feeds(self):
    """
    Synchronize all active iCal feeds.

    This task should be scheduled to run periodically (e.g., every hour).
    """
    logger.info('Starting scheduled iCal sync for all feeds')

    try:
        results = IcalImportService.sync_all()

        logger.info(
            f"iCal sync completed: "
            f"{results['success']}/{results['total']} successful, "
            f"{results['events_created']} created, "
            f"{results['events_updated']} updated"
        )

        return results

    except Exception as e:
        logger.error(f'iCal sync failed: {e}')
        raise self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes


@shared_task
def sync_single_ical_feed(ical_sync_id: int):
    """
    Synchronize a single iCal feed.

    Used for on-demand sync requests.
    """
    from .models import IcalSync, IcalSyncLog
    from django.utils import timezone

    logger.info(f'Starting iCal sync for sync ID {ical_sync_id}')

    try:
        ical_sync = IcalSync.objects.get(id=ical_sync_id)
    except IcalSync.DoesNotExist:
        logger.error(f'IcalSync {ical_sync_id} not found')
        return {'error': 'IcalSync not found'}

    created, updated, skipped, error = IcalImportService.sync_ical(ical_sync)

    # Create log entry
    log_status = IcalSyncLog.Status.SUCCESS if not error else IcalSyncLog.Status.FAILED
    IcalSyncLog.objects.create(
        ical_sync=ical_sync,
        status=log_status,
        events_found=created + updated + skipped,
        events_created=created,
        events_updated=updated,
        events_skipped=skipped,
        error_message=error,
    )

    # Update sync record
    ical_sync.last_synced_at = timezone.now()
    ical_sync.sync_count += 1
    ical_sync.last_error = error
    ical_sync.status = IcalSync.SyncStatus.ERROR if error else IcalSync.SyncStatus.ACTIVE
    ical_sync.save()

    logger.info(
        f"iCal sync {ical_sync_id} completed: "
        f"{created} created, {updated} updated"
    )

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'error': error,
    }
