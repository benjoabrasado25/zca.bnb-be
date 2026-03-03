"""Migrate existing city data to City model."""

from django.db import migrations


def migrate_cities_forward(apps, schema_editor):
    """Create City records from existing listing city names and link them."""
    Listing = apps.get_model('listings', 'Listing')
    City = apps.get_model('listings', 'City')

    # Get unique city names from existing listings
    city_names = Listing.objects.exclude(
        city_name_old__isnull=True
    ).exclude(
        city_name_old=''
    ).values_list('city_name_old', flat=True).distinct()

    # Create City records
    city_map = {}
    for city_name in city_names:
        city, _ = City.objects.get_or_create(
            name=city_name,
            defaults={
                'province': 'Negros Occidental',  # Default province
                'country': 'Philippines',
                'is_active': True,
            }
        )
        city_map[city_name] = city

    # Update listings to use the new City foreign key
    for listing in Listing.objects.exclude(city_name_old__isnull=True).exclude(city_name_old=''):
        if listing.city_name_old in city_map:
            listing.city = city_map[listing.city_name_old]
            listing.save(update_fields=['city'])


def migrate_cities_backward(apps, schema_editor):
    """Reverse migration - copy city names back to old field."""
    Listing = apps.get_model('listings', 'Listing')

    for listing in Listing.objects.filter(city__isnull=False):
        listing.city_name_old = listing.city.name
        listing.save(update_fields=['city_name_old'])


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0003_add_city_and_airbnb_fields'),
    ]

    operations = [
        migrations.RunPython(migrate_cities_forward, migrate_cities_backward),
    ]
