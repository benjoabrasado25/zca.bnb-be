# Drop ALL amadeus columns - we don't need them anymore

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0009_fix_amadeus_hotel_id'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_hotel_id;",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_chain_code;",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_brand_code;",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_dupes_id;",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_geonames_id;",
            reverse_sql="SELECT 1;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE listings DROP COLUMN IF EXISTS amadeus_last_update;",
            reverse_sql="SELECT 1;",
        ),
    ]
