"""Listing serializers for ZCA BnB."""

from rest_framework import serializers

from users.serializers import PublicUserSerializer
from .models import City, Listing, ListingImage, ListingAmenity, ListingAmenityMapping


class CitySerializer(serializers.ModelSerializer):
    """Serializer for cities."""

    class Meta:
        model = City
        fields = ['id', 'name', 'province', 'country']


class ListingImageSerializer(serializers.ModelSerializer):
    """Serializer for listing images."""

    class Meta:
        model = ListingImage
        fields = ['id', 'image', 'caption', 'is_primary', 'order']
        read_only_fields = ['id']


class ListingAmenitySerializer(serializers.ModelSerializer):
    """Serializer for amenities."""

    class Meta:
        model = ListingAmenity
        fields = ['id', 'name', 'icon', 'category']


class ListingListSerializer(serializers.ModelSerializer):
    """Serializer for listing list view (minimal data)."""

    host = PublicUserSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id',
            'slug',
            'title',
            'city',
            'neighborhood',
            'price_per_night',
            'currency',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            'property_type',
            'property_category',
            'is_instant_bookable',
            'is_featured',
            'host',
            'primary_image',
            'latitude',
            'longitude',
        ]

    def get_primary_image(self, obj):
        primary = obj.images.filter(is_primary=True).first()
        if not primary:
            primary = obj.images.first()
        if primary:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(primary.image.url)
            return primary.image.url
        return None


class ListingDetailSerializer(serializers.ModelSerializer):
    """Serializer for listing detail view (full data)."""

    host = PublicUserSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    amenities = serializers.SerializerMethodField()
    booked_dates = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id',
            'slug',
            'title',
            'description',
            'property_type',
            'property_category',
            'address',
            'city',
            'neighborhood',
            'postal_code',
            'latitude',
            'longitude',
            'price_per_night',
            'cleaning_fee',
            'service_fee_percent',
            'currency',
            'weekly_discount',
            'monthly_discount',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            # Property details
            'space_description',
            'guest_access',
            'interaction_with_guests',
            'other_things_to_note',
            'neighborhood_overview',
            'getting_around',
            # Rules
            'minimum_nights',
            'maximum_nights',
            'check_in_time',
            'check_out_time',
            # House rules
            'pets_allowed',
            'smoking_allowed',
            'parties_allowed',
            'children_allowed',
            'infants_allowed',
            'additional_rules',
            'cancellation_policy',
            # Status
            'status',
            'is_instant_bookable',
            'is_featured',
            'host',
            'images',
            'amenities',
            'booked_dates',
            'booking_url',
            'airbnb_url',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'host', 'created_at', 'updated_at']

    def get_amenities(self, obj):
        mappings = obj.amenity_mappings.select_related('amenity').all()
        return ListingAmenitySerializer([m.amenity for m in mappings], many=True).data

    def get_booked_dates(self, obj):
        """
        Get booked date ranges from confirmed/pending bookings.

        Returns a list of objects with 'start' and 'end' date strings.
        """
        from datetime import date
        from bookings.models import Booking

        # Get all confirmed and pending bookings for this listing
        bookings = Booking.objects.filter(
            listing=obj,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
            check_out__gte=date.today(),
        ).order_by('check_in')

        # Return date ranges
        return [
            {
                'start': booking.check_in.isoformat(),
                'end': booking.check_out.isoformat(),
            }
            for booking in bookings
        ]


class ListingCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating listings."""

    amenity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )
    city_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = Listing
        fields = [
            'title',
            'description',
            'property_type',
            'property_category',
            'address',
            'city_id',
            'neighborhood',
            'postal_code',
            'latitude',
            'longitude',
            'price_per_night',
            'cleaning_fee',
            'service_fee_percent',
            'currency',
            'weekly_discount',
            'monthly_discount',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            # Property details
            'space_description',
            'guest_access',
            'interaction_with_guests',
            'other_things_to_note',
            'neighborhood_overview',
            'getting_around',
            # Rules
            'minimum_nights',
            'maximum_nights',
            'check_in_time',
            'check_out_time',
            # House rules
            'pets_allowed',
            'smoking_allowed',
            'parties_allowed',
            'children_allowed',
            'infants_allowed',
            'additional_rules',
            'cancellation_policy',
            # Status
            'status',
            'is_instant_bookable',
            'amenity_ids',
        ]

    def create(self, validated_data):
        amenity_ids = validated_data.pop('amenity_ids', [])
        city_id = validated_data.pop('city_id', None)

        if city_id:
            validated_data['city_id'] = city_id

        listing = Listing.objects.create(**validated_data)

        # Add amenities
        for amenity_id in amenity_ids:
            ListingAmenityMapping.objects.create(
                listing=listing,
                amenity_id=amenity_id,
            )

        return listing

    def update(self, instance, validated_data):
        amenity_ids = validated_data.pop('amenity_ids', None)
        city_id = validated_data.pop('city_id', None)

        if city_id:
            validated_data['city_id'] = city_id

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update amenities if provided
        if amenity_ids is not None:
            instance.amenity_mappings.all().delete()
            for amenity_id in amenity_ids:
                ListingAmenityMapping.objects.create(
                    listing=instance,
                    amenity_id=amenity_id,
                )

        return instance


class ListingCalendarSerializer(serializers.Serializer):
    """Serializer for calendar/availability data."""

    start = serializers.DateField()
    end = serializers.DateField()
    type = serializers.CharField(read_only=True)
