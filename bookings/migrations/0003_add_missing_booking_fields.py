"""Add missing fields to Booking model."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_add_exclusion_constraint'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='guest_id_document',
            field=models.ForeignKey(
                blank=True,
                help_text='Guest ID document used for verification',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='users.GuestID',
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='message_to_host',
            field=models.TextField(blank=True, help_text='Initial message from guest to host'),
        ),
    ]
