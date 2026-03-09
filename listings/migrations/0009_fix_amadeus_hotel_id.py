# Fix ALL amadeus columns - make them nullable

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0008_add_klook_affiliate_url'),
    ]

    operations = [
        # Fix all amadeus columns at once
        migrations.RunSQL(
            sql="""
                DO $$
                DECLARE
                    col_name TEXT;
                BEGIN
                    FOR col_name IN
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'listings'
                        AND column_name LIKE 'amadeus%'
                    LOOP
                        EXECUTE format('ALTER TABLE listings ALTER COLUMN %I DROP NOT NULL', col_name);
                        EXECUTE format('ALTER TABLE listings ALTER COLUMN %I SET DEFAULT %L', col_name, '');
                    END LOOP;
                END $$;
            """,
            reverse_sql="SELECT 1;",
        ),
    ]
