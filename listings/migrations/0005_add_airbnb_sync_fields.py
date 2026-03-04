"""Add Airbnb sync, iCal, ratings, and additional listing fields.

This migration checks if fields already exist before adding them.
"""

import uuid
from django.db import migrations, models, connection


def field_exists(table_name, field_name):
    """Check if a field exists in a table."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, [table_name, field_name])
        return cursor.fetchone() is not None


class ConditionalAddField(migrations.AddField):
    """AddField that only runs if the field doesn't exist."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if not field_exists(self.model_name + 's', self.name):
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if field_exists(self.model_name + 's', self.name):
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_migrate_city_data'),
    ]

    operations = [
        # Use raw SQL to add fields only if they don't exist
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                -- Airbnb Integration
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='airbnb_id') THEN
                    ALTER TABLE listings ADD COLUMN airbnb_id VARCHAR(50) DEFAULT '' NOT NULL;
                    CREATE INDEX IF NOT EXISTS listings_airbnb_id_idx ON listings(airbnb_id);
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='airbnb_url') THEN
                    ALTER TABLE listings ADD COLUMN airbnb_url VARCHAR(500) DEFAULT '' NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='booking_url') THEN
                    ALTER TABLE listings ADD COLUMN booking_url VARCHAR(500) DEFAULT '' NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='last_synced') THEN
                    ALTER TABLE listings ADD COLUMN last_synced TIMESTAMP WITH TIME ZONE NULL;
                END IF;

                -- iCal Integration
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='ical_export_token') THEN
                    ALTER TABLE listings ADD COLUMN ical_export_token UUID DEFAULT gen_random_uuid() NOT NULL UNIQUE;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='ical_url') THEN
                    ALTER TABLE listings ADD COLUMN ical_url VARCHAR(500) DEFAULT '' NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='ical_last_synced') THEN
                    ALTER TABLE listings ADD COLUMN ical_last_synced TIMESTAMP WITH TIME ZONE NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='booked_dates') THEN
                    ALTER TABLE listings ADD COLUMN booked_dates JSONB DEFAULT '[]'::jsonb NOT NULL;
                END IF;

                -- Ratings & Reviews
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating') THEN
                    ALTER TABLE listings ADD COLUMN rating DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='reviews_count') THEN
                    ALTER TABLE listings ADD COLUMN reviews_count INTEGER DEFAULT 0 NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_accuracy') THEN
                    ALTER TABLE listings ADD COLUMN rating_accuracy DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_cleanliness') THEN
                    ALTER TABLE listings ADD COLUMN rating_cleanliness DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_checkin') THEN
                    ALTER TABLE listings ADD COLUMN rating_checkin DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_communication') THEN
                    ALTER TABLE listings ADD COLUMN rating_communication DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_location') THEN
                    ALTER TABLE listings ADD COLUMN rating_location DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='rating_value') THEN
                    ALTER TABLE listings ADD COLUMN rating_value DECIMAL(3,2) NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='reviews') THEN
                    ALTER TABLE listings ADD COLUMN reviews JSONB DEFAULT '[]'::jsonb NOT NULL;
                END IF;

                -- Property Highlights
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='highlights') THEN
                    ALTER TABLE listings ADD COLUMN highlights JSONB DEFAULT '[]'::jsonb NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='square_feet') THEN
                    ALTER TABLE listings ADD COLUMN square_feet INTEGER NULL;
                END IF;

                -- Check-in Details
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='self_checkin') THEN
                    ALTER TABLE listings ADD COLUMN self_checkin BOOLEAN DEFAULT FALSE NOT NULL;
                END IF;

                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='listings' AND column_name='checkin_method') THEN
                    ALTER TABLE listings ADD COLUMN checkin_method VARCHAR(255) DEFAULT '' NOT NULL;
                END IF;
            END $$;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
