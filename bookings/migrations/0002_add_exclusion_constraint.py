"""
Migration to add PostgreSQL exclusion constraint for preventing double bookings.

This uses the btree_gist extension and an exclusion constraint to prevent
overlapping date ranges for the same listing at the database level.

IMPORTANT: This constraint ensures NO overlapping bookings can exist for the same listing,
regardless of whether the booking is created manually or via iCal import.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0001_initial'),
    ]

    operations = [
        # Enable btree_gist extension (required for exclusion constraints with non-geometric types)
        migrations.RunSQL(
            sql='CREATE EXTENSION IF NOT EXISTS btree_gist;',
            reverse_sql='DROP EXTENSION IF EXISTS btree_gist;',
        ),

        # Add exclusion constraint to prevent overlapping bookings
        # Uses '[)' range: includes check_in, excludes check_out (standard hotel booking logic)
        # Only applies to non-cancelled bookings (confirmed and pending)
        # This works for BOTH manual bookings AND iCal imported bookings
        migrations.RunSQL(
            sql='''
                ALTER TABLE bookings
                ADD CONSTRAINT prevent_double_booking
                EXCLUDE USING gist (
                    listing_id WITH =,
                    daterange(check_in, check_out, '[)') WITH &&
                )
                WHERE (status NOT IN ('cancelled'));
            ''',
            reverse_sql='ALTER TABLE bookings DROP CONSTRAINT IF EXISTS prevent_double_booking;',
        ),

        # Add exclusion constraint for blocked dates to prevent overlapping blocks
        # Uses '[]' range: includes both start and end dates
        migrations.RunSQL(
            sql='''
                ALTER TABLE blocked_dates
                ADD CONSTRAINT prevent_overlapping_blocks
                EXCLUDE USING gist (
                    listing_id WITH =,
                    daterange(start_date, end_date, '[]') WITH &&
                );
            ''',
            reverse_sql='ALTER TABLE blocked_dates DROP CONSTRAINT IF EXISTS prevent_overlapping_blocks;',
        ),

        # Add index for faster date range queries
        migrations.RunSQL(
            sql='''
                CREATE INDEX IF NOT EXISTS bookings_listing_dates_idx
                ON bookings (listing_id, check_in, check_out)
                WHERE status NOT IN ('cancelled');
            ''',
            reverse_sql='DROP INDEX IF EXISTS bookings_listing_dates_idx;',
        ),

        # Add index for external_uid lookups (iCal deduplication)
        migrations.RunSQL(
            sql='''
                CREATE INDEX IF NOT EXISTS bookings_external_uid_idx
                ON bookings (listing_id, external_uid)
                WHERE external_uid != '';
            ''',
            reverse_sql='DROP INDEX IF EXISTS bookings_external_uid_idx;',
        ),
    ]
