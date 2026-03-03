"""Add host approval workflow fields."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='host_status',
            field=models.CharField(
                choices=[
                    ('not_applied', 'Not Applied'),
                    ('pending', 'Pending Approval'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='not_applied',
                help_text='Admin approval status for hosting privileges',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='host_application_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='host_approved_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='host_rejection_reason',
            field=models.TextField(blank=True),
        ),
    ]
