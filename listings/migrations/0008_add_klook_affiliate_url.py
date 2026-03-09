# Generated migration for Google Places and Klook affiliate fields

from django.db import migrations, models


def check_column_exists(apps, schema_editor):
    """Check if columns already exist before migration runs."""
    pass  # We use SeparateDatabaseAndState for safety


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_add_city_image_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'listings_listing' AND column_name = 'google_place_id'
                    ) THEN
                        ALTER TABLE listings_listing ADD COLUMN google_place_id VARCHAR(255) DEFAULT '';
                        CREATE INDEX IF NOT EXISTS listings_listing_google_place_id_idx ON listings_listing(google_place_id);
                    END IF;
                END $$;
            """,
            reverse_sql="ALTER TABLE listings_listing DROP COLUMN IF EXISTS google_place_id;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'listings_listing' AND column_name = 'google_maps_url'
                    ) THEN
                        ALTER TABLE listings_listing ADD COLUMN google_maps_url VARCHAR(500) DEFAULT '';
                    END IF;
                END $$;
            """,
            reverse_sql="ALTER TABLE listings_listing DROP COLUMN IF EXISTS google_maps_url;",
        ),
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'listings_listing' AND column_name = 'klook_affiliate_url'
                    ) THEN
                        ALTER TABLE listings_listing ADD COLUMN klook_affiliate_url VARCHAR(1000) DEFAULT '';
                    END IF;
                END $$;
            """,
            reverse_sql="ALTER TABLE listings_listing DROP COLUMN IF EXISTS klook_affiliate_url;",
        ),
    ]
