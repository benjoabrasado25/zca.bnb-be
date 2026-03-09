# Generated migration for Google Places and Klook affiliate fields
# Safe migration that checks for existing columns

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_add_city_image_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE listings ADD COLUMN IF NOT EXISTS google_place_id VARCHAR(255) DEFAULT '';",
            reverse_sql="SELECT 1;",  # No-op for reverse
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS listings_google_place_id_idx ON listings(google_place_id);",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings ADD COLUMN IF NOT EXISTS google_maps_url VARCHAR(500) DEFAULT '';",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings ADD COLUMN IF NOT EXISTS klook_affiliate_url VARCHAR(1000) DEFAULT '';",
            reverse_sql="SELECT 1;",
        ),
    ]
