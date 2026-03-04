"""Add slug field to Listing model."""

from django.db import migrations, models, connection
from django.utils.text import slugify


def generate_slugs(apps, schema_editor):
    """Generate slugs for existing listings using raw SQL."""
    with connection.cursor() as cursor:
        # Get all listings without slugs
        cursor.execute("SELECT id, title FROM listings WHERE slug IS NULL OR slug = ''")
        listings = cursor.fetchall()

        for listing_id, title in listings:
            base_slug = slugify(title) if title else f'listing-{listing_id}'
            if not base_slug:
                base_slug = f'listing-{listing_id}'

            slug = base_slug
            counter = 1

            # Check for duplicates
            while True:
                cursor.execute(
                    "SELECT COUNT(*) FROM listings WHERE slug = %s AND id != %s",
                    [slug, listing_id]
                )
                if cursor.fetchone()[0] == 0:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1

            # Update the listing
            cursor.execute(
                "UPDATE listings SET slug = %s WHERE id = %s",
                [slug, listing_id]
            )


def reverse_slugs(apps, schema_editor):
    """Reverse migration - no-op for safety."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0005_add_airbnb_sync_fields'),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: Add column if not exists
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'listings' AND column_name = 'slug'
                    ) THEN
                        ALTER TABLE listings ADD COLUMN slug VARCHAR(280);
                    END IF;
                END $$;
            """,
            # Reverse: Drop column
            reverse_sql="ALTER TABLE listings DROP COLUMN IF EXISTS slug;",
        ),
        # Generate slugs for existing records using raw SQL
        migrations.RunPython(generate_slugs, reverse_slugs),
        # Add unique constraint if not exists
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE tablename = 'listings' AND indexname = 'listings_slug_key'
                    ) THEN
                        CREATE UNIQUE INDEX listings_slug_key ON listings (slug);
                    END IF;
                END $$;
            """,
            reverse_sql="DROP INDEX IF EXISTS listings_slug_key;",
        ),
    ]
