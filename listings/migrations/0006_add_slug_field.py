"""Add slug field to Listing model."""

from django.db import migrations, models, connection
from django.utils.text import slugify


def column_exists(table_name, column_name):
    """Check if a column exists in the table."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, [table_name, column_name])
        return cursor.fetchone() is not None


def generate_slugs(apps, schema_editor):
    """Generate slugs for existing listings."""
    Listing = apps.get_model('listings', 'Listing')

    for listing in Listing.objects.all():
        if listing.slug:  # Skip if slug already exists
            continue

        base_slug = slugify(listing.title) if listing.title else f'listing-{listing.pk}'
        if not base_slug:
            base_slug = f'listing-{listing.pk}'

        slug = base_slug
        counter = 1

        while Listing.objects.filter(slug=slug).exclude(pk=listing.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        listing.slug = slug
        listing.save(update_fields=['slug'])


def reverse_slugs(apps, schema_editor):
    """Reverse migration - clear slugs."""
    pass  # No-op for safety


def add_slug_field(apps, schema_editor):
    """Add slug field if it doesn't exist."""
    if column_exists('listings', 'slug'):
        # Column already exists, just populate empty slugs
        generate_slugs(apps, schema_editor)
    else:
        # Column doesn't exist - this shouldn't happen since we use AddField
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
        # Generate slugs for existing records
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
