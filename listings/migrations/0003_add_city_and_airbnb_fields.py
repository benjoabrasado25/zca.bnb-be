"""Add City model and Airbnb-style listing fields."""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0002_add_listing_approval'),
    ]

    operations = [
        # Create City model
        migrations.CreateModel(
            name='City',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('province', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(default='Philippines', max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'City',
                'verbose_name_plural': 'Cities',
                'db_table': 'cities',
                'ordering': ['order', 'name'],
            },
        ),

        # Add new fields to Listing
        migrations.AddField(
            model_name='listing',
            name='property_category',
            field=models.CharField(
                choices=[
                    ('house', 'House'),
                    ('apartment', 'Apartment'),
                    ('guesthouse', 'Guesthouse'),
                    ('hotel', 'Hotel'),
                    ('villa', 'Villa'),
                    ('condo', 'Condo'),
                    ('townhouse', 'Townhouse'),
                    ('cottage', 'Cottage'),
                    ('cabin', 'Cabin'),
                    ('resort', 'Resort'),
                    ('hostel', 'Hostel'),
                    ('bnb', 'Bed & Breakfast'),
                    ('farm_stay', 'Farm Stay'),
                    ('boat', 'Boat'),
                    ('camper', 'Camper/RV'),
                    ('treehouse', 'Treehouse'),
                    ('tent', 'Tent'),
                    ('other', 'Other'),
                ],
                default='house',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='neighborhood',
            field=models.CharField(blank=True, help_text='Specific area/neighborhood', max_length=200),
        ),
        migrations.AddField(
            model_name='listing',
            name='service_fee_percent',
            field=models.DecimalField(decimal_places=2, default=10.0, help_text='Service fee percentage charged to guests', max_digits=4),
        ),
        migrations.AddField(
            model_name='listing',
            name='weekly_discount',
            field=models.PositiveIntegerField(default=0, help_text='Discount % for 7+ nights'),
        ),
        migrations.AddField(
            model_name='listing',
            name='monthly_discount',
            field=models.PositiveIntegerField(default=0, help_text='Discount % for 28+ nights'),
        ),
        migrations.AddField(
            model_name='listing',
            name='space_description',
            field=models.TextField(blank=True, help_text='Describe the space guests will have access to'),
        ),
        migrations.AddField(
            model_name='listing',
            name='guest_access',
            field=models.TextField(blank=True, help_text='What areas can guests access?'),
        ),
        migrations.AddField(
            model_name='listing',
            name='interaction_with_guests',
            field=models.TextField(blank=True, help_text='How much will you interact with guests?'),
        ),
        migrations.AddField(
            model_name='listing',
            name='other_things_to_note',
            field=models.TextField(blank=True, help_text='Other important details'),
        ),
        migrations.AddField(
            model_name='listing',
            name='neighborhood_overview',
            field=models.TextField(blank=True, help_text='Describe the neighborhood'),
        ),
        migrations.AddField(
            model_name='listing',
            name='getting_around',
            field=models.TextField(blank=True, help_text='Transportation options'),
        ),
        migrations.AddField(
            model_name='listing',
            name='pets_allowed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='listing',
            name='smoking_allowed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='listing',
            name='parties_allowed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='listing',
            name='children_allowed',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='infants_allowed',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='listing',
            name='additional_rules',
            field=models.TextField(blank=True, help_text='Any additional house rules'),
        ),
        migrations.AddField(
            model_name='listing',
            name='cancellation_policy',
            field=models.CharField(
                choices=[
                    ('flexible', 'Flexible - Full refund 1 day prior'),
                    ('moderate', 'Moderate - Full refund 5 days prior'),
                    ('strict', 'Strict - 50% refund up to 1 week prior'),
                    ('super_strict', 'Super Strict - No refund'),
                ],
                default='moderate',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='is_featured',
            field=models.BooleanField(default=False, help_text='Featured on homepage'),
        ),

        # Rename city CharField to city_name temporarily
        migrations.RenameField(
            model_name='listing',
            old_name='city',
            new_name='city_name_old',
        ),

        # Add new city ForeignKey field
        migrations.AddField(
            model_name='listing',
            name='city',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='listings',
                to='listings.city',
            ),
        ),

        # Remove old province and country fields (now in City model)
        migrations.RemoveField(
            model_name='listing',
            name='province',
        ),
        migrations.RemoveField(
            model_name='listing',
            name='country',
        ),

        # Keep city_name_old for now - can be used for data migration
        # Remove after data migration is done
    ]
