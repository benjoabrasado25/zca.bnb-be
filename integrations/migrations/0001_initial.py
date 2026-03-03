"""Initial migration for integrations."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IcalSync',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[
                    ('airbnb', 'Airbnb'),
                    ('booking_com', 'Booking.com'),
                    ('vrbo', 'VRBO'),
                    ('other', 'Other'),
                ], default='airbnb', max_length=20)),
                ('airbnb_import_url', models.URLField(help_text='iCal URL from Airbnb or other platform', max_length=1000)),
                ('status', models.CharField(choices=[
                    ('active', 'Active'),
                    ('paused', 'Paused'),
                    ('error', 'Error'),
                ], default='active', max_length=20)),
                ('last_synced_at', models.DateTimeField(blank=True, null=True)),
                ('last_error', models.TextField(blank=True)),
                ('sync_count', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ical_syncs', to='listings.listing')),
            ],
            options={
                'verbose_name': 'iCal Sync',
                'verbose_name_plural': 'iCal Syncs',
                'db_table': 'ical_syncs',
                'unique_together': {('listing', 'airbnb_import_url')},
            },
        ),
        migrations.CreateModel(
            name='IcalSyncLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[
                    ('success', 'Success'),
                    ('failed', 'Failed'),
                    ('partial', 'Partial'),
                ], max_length=20)),
                ('events_found', models.PositiveIntegerField(default=0)),
                ('events_created', models.PositiveIntegerField(default=0)),
                ('events_updated', models.PositiveIntegerField(default=0)),
                ('events_skipped', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ical_sync', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='integrations.icalsync')),
            ],
            options={
                'db_table': 'ical_sync_logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
