"""Listing serializers for ZCA BnB."""

from rest_framework import serializers

from users.serializers import PublicUserSerializer
from .models import Listing, ListingImage, ListingAmenity, ListingAmenityMapping


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
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id',
            'title',
            'city',
            'province',
            'price_per_night',
            'currency',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            'property_type',
            'is_instant_bookable',
            'host',
            'primary_image',
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
    images = ListingImageSerializer(many=True, read_only=True)
    amenities = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            'id',
            'title',
            'description',
            'property_type',
            'address',
            'city',
            'province',
            'postal_code',
            'country',
            'latitude',
            'longitude',
            'price_per_night',
            'cleaning_fee',
            'currency',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            'minimum_nights',
            'maximum_nights',
            'check_in_time',
            'check_out_time',
            'status',
            'is_instant_bookable',
            'host',
            'images',
            'amenities',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'host', 'created_at', 'updated_at']

    def get_amenities(self, obj):
        mappings = obj.amenity_mappings.select_related('amenity').all()
        return ListingAmenitySerializer([m.amenity for m in mappings], many=True).data


class ListingCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating listings."""

    amenity_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Listing
        fields = [
            'title',
            'description',
            'property_type',
            'address',
            'city',
            'province',
            'postal_code',
            'country',
            'latitude',
            'longitude',
            'price_per_night',
            'cleaning_fee',
            'currency',
            'max_guests',
            'bedrooms',
            'beds',
            'bathrooms',
            'minimum_nights',
            'maximum_nights',
            'check_in_time',
            'check_out_time',
            'status',
            'is_instant_bookable',
            'amenity_ids',
        ]

    def create(self, validated_data):
        amenity_ids = validated_data.pop('amenity_ids', [])
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
