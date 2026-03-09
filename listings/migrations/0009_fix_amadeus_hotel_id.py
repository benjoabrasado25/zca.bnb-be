# Fix amadeus_hotel_id column - make it nullable or add default

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0008_add_klook_affiliate_url'),
    ]

    operations = [
        # Make amadeus_hotel_id nullable if it exists
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'listings' AND column_name = 'amadeus_hotel_id'
                    ) THEN
                        ALTER TABLE listings ALTER COLUMN amadeus_hotel_id DROP NOT NULL;
                        ALTER TABLE listings ALTER COLUMN amadeus_hotel_id SET DEFAULT '';
                    END IF;
                END $$;
            """,
            reverse_sql="SELECT 1;",
        ),
    ]
