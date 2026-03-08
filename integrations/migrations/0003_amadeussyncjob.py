# Generated migration for AmadeusSyncJob model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0002_airbnbsyncjob'),
    ]

    operations = [
        migrations.CreateModel(
            name='AmadeusSyncJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('job_id', models.CharField(max_length=100, unique=True)),
                ('sync_type', models.CharField(choices=[('city_search', 'City Search'), ('hotel_list', 'Hotel List'), ('geocode', 'Geocode Search')], default='city_search', max_length=20)),
                ('city_code', models.CharField(blank=True, help_text='IATA city code (e.g., MNL)', max_length=10)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('radius', models.PositiveIntegerField(default=50, help_text='Search radius in km')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('succeeded', 'Succeeded'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('hotels_found', models.PositiveIntegerField(default=0)),
                ('hotels_created', models.PositiveIntegerField(default=0)),
                ('hotels_updated', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('raw_response', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Amadeus Sync Job',
                'verbose_name_plural': 'Amadeus Sync Jobs',
                'db_table': 'amadeus_sync_jobs',
                'ordering': ['-created_at'],
            },
        ),
    ]
