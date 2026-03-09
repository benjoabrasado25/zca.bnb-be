# Generated migration for GooglePlacesSyncJob model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0002_airbnbsyncjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='GooglePlacesSyncJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.CharField(max_length=100, unique=True)),
                ('search_query', models.CharField(help_text='Search query (e.g., "hotels in Manila")', max_length=255)),
                ('city_name', models.CharField(blank=True, max_length=100)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('hotels_found', models.PositiveIntegerField(default=0)),
                ('hotels_created', models.PositiveIntegerField(default=0)),
                ('hotels_updated', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Google Places Sync Job',
                'verbose_name_plural': 'Google Places Sync Jobs',
                'db_table': 'google_places_sync_jobs',
                'ordering': ['-created_at'],
            },
        ),
    ]
