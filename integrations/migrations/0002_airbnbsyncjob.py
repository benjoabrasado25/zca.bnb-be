"""Add AirbnbSyncJob model."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AirbnbSyncJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('run_id', models.CharField(max_length=100, unique=True)),
                ('airbnb_urls', models.JSONField(default=list, help_text='List of Airbnb URLs to sync')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('running', 'Running'),
                        ('succeeded', 'Succeeded'),
                        ('failed', 'Failed'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('listings_created', models.PositiveIntegerField(default=0)),
                ('listings_updated', models.PositiveIntegerField(default=0)),
                ('error_message', models.TextField(blank=True)),
                ('raw_response', models.JSONField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Airbnb Sync Job',
                'verbose_name_plural': 'Airbnb Sync Jobs',
                'db_table': 'airbnb_sync_jobs',
                'ordering': ['-created_at'],
            },
        ),
    ]
