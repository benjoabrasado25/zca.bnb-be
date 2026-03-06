"""Add image, description, and is_featured fields to City model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0006_add_slug_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='city',
            name='image',
            field=models.ImageField(blank=True, help_text='City cover image for homepage', null=True, upload_to='city_images/'),
        ),
        migrations.AddField(
            model_name='city',
            name='description',
            field=models.TextField(blank=True, help_text='Short description for homepage display'),
        ),
        migrations.AddField(
            model_name='city',
            name='is_featured',
            field=models.BooleanField(default=False, help_text='Show on homepage'),
        ),
    ]
