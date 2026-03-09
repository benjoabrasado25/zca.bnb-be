# Generated migration for Google Places and Klook affiliate fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_add_city_image_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='google_place_id',
            field=models.CharField(blank=True, db_index=True, help_text='Google Places ID', max_length=255),
        ),
        migrations.AddField(
            model_name='listing',
            name='google_maps_url',
            field=models.URLField(blank=True, help_text='Google Maps URL', max_length=500),
        ),
        migrations.AddField(
            model_name='listing',
            name='klook_affiliate_url',
            field=models.URLField(blank=True, help_text='Klook affiliate booking URL (add manually)', max_length=1000),
        ),
    ]
