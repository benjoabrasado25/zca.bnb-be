"""Add slug field to Listing model."""

from django.db import migrations, models
from django.utils.text import slugify


def generate_slugs(apps, schema_editor):
    """Generate slugs for existing listings."""
    Listing = apps.get_model('listings', 'Listing')

    for listing in Listing.objects.all():
        base_slug = slugify(listing.title)
        slug = base_slug
        counter = 1

        while Listing.objects.filter(slug=slug).exclude(pk=listing.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        listing.slug = slug
        listing.save(update_fields=['slug'])


def reverse_slugs(apps, schema_editor):
    """Reverse migration - clear slugs."""
    Listing = apps.get_model('listings', 'Listing')
    Listing.objects.update(slug='')


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0005_add_airbnb_sync_fields'),
    ]

    operations = [
        # First add the field as nullable
        migrations.AddField(
            model_name='listing',
            name='slug',
            field=models.SlugField(blank=True, max_length=280, null=True),
        ),
        # Generate slugs for existing records
        migrations.RunPython(generate_slugs, reverse_slugs),
        # Make the field unique and non-nullable
        migrations.AlterField(
            model_name='listing',
            name='slug',
            field=models.SlugField(blank=True, max_length=280, unique=True),
        ),
    ]
