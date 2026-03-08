# Generated migration for Amadeus integration fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_add_city_image_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='amadeus_hotel_id',
            field=models.CharField(blank=True, db_index=True, help_text='Amadeus hotel ID (e.g., RTMANILA)', max_length=20),
        ),
        migrations.AddField(
            model_name='listing',
            name='amadeus_chain_code',
            field=models.CharField(blank=True, help_text='Hotel chain code', max_length=10),
        ),
        migrations.AddField(
            model_name='listing',
            name='amadeus_last_synced',
            field=models.DateTimeField(blank=True, help_text='Last Amadeus sync timestamp', null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='klook_affiliate_url',
            field=models.URLField(blank=True, help_text='Klook affiliate booking URL (add manually)', max_length=1000),
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['amadeus_hotel_id'], name='listings_amadeus_c1b2a3_idx'),
        ),
    ]
