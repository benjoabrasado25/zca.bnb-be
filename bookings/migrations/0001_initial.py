"""Initial migration for bookings with PostgreSQL exclusion constraint."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('check_in', models.DateField()),
                ('check_out', models.DateField()),
                ('price_per_night', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cleaning_fee', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_price', models.DecimalField(decimal_places=2, max_digits=12)),
                ('currency', models.CharField(default='PHP', max_length=3)),
                ('num_guests', models.PositiveIntegerField(default=1)),
                ('guest_name', models.CharField(blank=True, max_length=255)),
                ('guest_email', models.EmailField(blank=True, max_length=254)),
                ('guest_phone', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[
                    ('pending', 'Pending'),
                    ('confirmed', 'Confirmed'),
                    ('cancelled', 'Cancelled'),
                    ('completed', 'Completed'),
                ], default='pending', max_length=20)),
                ('source', models.CharField(choices=[
                    ('manual', 'Manual'),
                    ('airbnb_ical', 'Airbnb iCal'),
                    ('booking_com_ical', 'Booking.com iCal'),
                    ('other_ical', 'Other iCal'),
                ], default='manual', max_length=20)),
                ('external_uid', models.CharField(blank=True, help_text='UID from external iCal source for deduplication', max_length=255)),
                ('special_requests', models.TextField(blank=True)),
                ('host_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('guest', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to=settings.AUTH_USER_MODEL)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='listings.listing')),
            ],
            options={
                'verbose_name': 'Booking',
                'verbose_name_plural': 'Bookings',
                'db_table': 'bookings',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BlockedDate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocked_dates', to='listings.listing')),
            ],
            options={
                'db_table': 'blocked_dates',
                'ordering': ['start_date'],
            },
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['listing', 'check_in', 'check_out'], name='bookings_listing_7e1e1c_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['listing', 'status'], name='bookings_listing_d4e8a7_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['guest', 'status'], name='bookings_guest_i_8c1234_idx'),
        ),
        migrations.AddIndex(
            model_name='booking',
            index=models.Index(fields=['external_uid'], name='bookings_externa_abc123_idx'),
        ),
    ]
