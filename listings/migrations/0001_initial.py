"""Initial migration for listings."""

import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Listing',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField()),
                ('property_type', models.CharField(choices=[
                    ('entire_place', 'Entire Place'),
                    ('private_room', 'Private Room'),
                    ('shared_room', 'Shared Room'),
                ], default='entire_place', max_length=20)),
                ('address', models.CharField(max_length=500)),
                ('city', models.CharField(max_length=100)),
                ('province', models.CharField(blank=True, max_length=100)),
                ('postal_code', models.CharField(blank=True, max_length=20)),
                ('country', models.CharField(default='Philippines', max_length=100)),
                ('latitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ('price_per_night', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cleaning_fee', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('currency', models.CharField(default='PHP', max_length=3)),
                ('max_guests', models.PositiveIntegerField(default=1)),
                ('bedrooms', models.PositiveIntegerField(default=1)),
                ('beds', models.PositiveIntegerField(default=1)),
                ('bathrooms', models.DecimalField(decimal_places=1, default=1, max_digits=3)),
                ('minimum_nights', models.PositiveIntegerField(default=1)),
                ('maximum_nights', models.PositiveIntegerField(default=365)),
                ('check_in_time', models.TimeField(default='14:00')),
                ('check_out_time', models.TimeField(default='11:00')),
                ('status', models.CharField(choices=[
                    ('draft', 'Draft'),
                    ('active', 'Active'),
                    ('inactive', 'Inactive'),
                ], default='draft', max_length=20)),
                ('is_instant_bookable', models.BooleanField(default=False)),
                ('ical_export_token', models.UUIDField(default=uuid.uuid4, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('host', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Listing',
                'verbose_name_plural': 'Listings',
                'db_table': 'listings',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ListingAmenity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('icon', models.CharField(blank=True, max_length=50)),
                ('category', models.CharField(choices=[
                    ('essentials', 'Essentials'),
                    ('features', 'Features'),
                    ('location', 'Location'),
                    ('safety', 'Safety'),
                ], default='essentials', max_length=20)),
            ],
            options={
                'verbose_name_plural': 'Listing Amenities',
                'db_table': 'listing_amenities',
            },
        ),
        migrations.CreateModel(
            name='ListingImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='listing_images/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('is_primary', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='listings.listing')),
            ],
            options={
                'db_table': 'listing_images',
                'ordering': ['order', 'created_at'],
            },
        ),
        migrations.CreateModel(
            name='ListingAmenityMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amenity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='listing_mappings', to='listings.listingamenity')),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='amenity_mappings', to='listings.listing')),
            ],
            options={
                'db_table': 'listing_amenity_mappings',
                'unique_together': {('listing', 'amenity')},
            },
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['city'], name='listings_city_idx'),
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['status'], name='listings_status_idx'),
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['price_per_night'], name='listings_price_idx'),
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(fields=['host', 'status'], name='listings_host_status_idx'),
        ),
    ]
