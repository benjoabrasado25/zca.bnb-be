"""Add Airbnb sync, iCal, ratings, and additional listing fields."""

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_migrate_city_data'),
    ]

    operations = [
        # Airbnb Integration
        migrations.AddField(
            model_name='listing',
            name='airbnb_id',
            field=models.CharField(blank=True, db_index=True, help_text='Airbnb listing ID', max_length=50),
        ),
        migrations.AddField(
            model_name='listing',
            name='airbnb_url',
            field=models.URLField(blank=True, help_text='Full Airbnb listing URL', max_length=500),
        ),
        migrations.AddField(
            model_name='listing',
            name='booking_url',
            field=models.URLField(blank=True, help_text='External booking URL', max_length=500),
        ),
        migrations.AddField(
            model_name='listing',
            name='last_synced',
            field=models.DateTimeField(blank=True, help_text='Last Apify sync timestamp', null=True),
        ),

        # iCal Integration
        migrations.AddField(
            model_name='listing',
            name='ical_export_token',
            field=models.UUIDField(default=uuid.uuid4, unique=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='ical_url',
            field=models.URLField(blank=True, help_text='iCal feed URL for availability sync', max_length=500),
        ),
        migrations.AddField(
            model_name='listing',
            name='ical_last_synced',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='booked_dates',
            field=models.JSONField(blank=True, default=list, help_text='JSON array of booked date ranges from iCal'),
        ),

        # Ratings & Reviews
        migrations.AddField(
            model_name='listing',
            name='rating',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Overall rating 0-5', max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='reviews_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_accuracy',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_cleanliness',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_checkin',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_communication',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_location',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='rating_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=3, null=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='reviews',
            field=models.JSONField(blank=True, default=list, help_text='JSON array of review objects'),
        ),

        # Property Highlights
        migrations.AddField(
            model_name='listing',
            name='highlights',
            field=models.JSONField(blank=True, default=list, help_text='JSON array of property highlights'),
        ),
        migrations.AddField(
            model_name='listing',
            name='square_feet',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),

        # Check-in Details
        migrations.AddField(
            model_name='listing',
            name='self_checkin',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='listing',
            name='checkin_method',
            field=models.CharField(blank=True, help_text='e.g., Lockbox, Smart lock, Doorman', max_length=255),
        ),

        # Add index for airbnb_id
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['airbnb_id'], name='listings_airbnb__e37e50_idx'),
        ),
    ]
