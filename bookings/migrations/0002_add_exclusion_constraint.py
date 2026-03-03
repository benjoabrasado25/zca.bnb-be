"""
Migration to add PostgreSQL exclusion constraint for preventing double bookings.

This uses the btree_gist extension and an exclusion constraint to prevent
overlapping date ranges for the same listing at the database level.

IMPORTANT: This constraint ensures NO overlapping bookings can exist for the same listing,
regardless of whether the booking is created manually or via iCal import.

NOTE: If btree_gist extension fails to create (permission denied), the migration
will skip it - the app will still work but without database-level double-booking prevention.
"""

from django.db import migrations


def create_extension_safe(apps, schema_editor):
    """Try to create btree_gist extension, skip if permission denied."""
    try:
        schema_editor.execute('CREATE EXTENSION IF NOT EXISTS btree_gist;')
    except Exception as e:
        print(f"Warning: Could not create btree_gist extension: {e}")
        print("Double-booking prevention at DB level will not be available.")


def create_booking_constraint(apps, schema_editor):
    """Try to create booking exclusion constraint."""
    try:
        schema_editor.execute('''
            ALTER TABLE bookings
            ADD CONSTRAINT prevent_double_booking
            EXCLUDE USING gist (
                listing_id WITH =,
                daterange(check_in, check_out, '[)') WITH &&
            )
            WHERE (status NOT IN ('cancelled'));
        ''')
    except Exception as e:
        print(f"Warning: Could not create booking constraint: {e}")


def create_blocked_dates_constraint(apps, schema_editor):
    """Try to create blocked dates exclusion constraint."""
    try:
        schema_editor.execute('''
            ALTER TABLE blocked_dates
            ADD CONSTRAINT prevent_overlapping_blocks
            EXCLUDE USING gist (
                listing_id WITH =,
                daterange(start_date, end_date, '[]') WITH &&
            );
        ''')
    except Exception as e:
        print(f"Warning: Could not create blocked dates constraint: {e}")


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0001_initial'),
    ]

    operations = [
        # Enable btree_gist extension (required for exclusion constraints)
        migrations.RunPython(create_extension_safe, migrations.RunPython.noop),

        # Add exclusion constraint to prevent overlapping bookings
        migrations.RunPython(create_booking_constraint, migrations.RunPython.noop),

        # Add exclusion constraint for blocked dates
        migrations.RunPython(create_blocked_dates_constraint, migrations.RunPython.noop),

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
