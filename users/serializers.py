"""User serializers for ZCA BnB."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import GuestID

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details."""

    is_host = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'user_type',
            'host_status',
            'is_host',
            'phone_number',
            'profile_picture',
            'bio',
            'is_verified',
            'created_at',
        ]
        read_only_fields = ['id', 'is_verified', 'created_at', 'host_status', 'is_host']


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'password',
            'password_confirm',
            'first_name',
            'last_name',
            'user_type',
            'phone_number',
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Passwords don't match."
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile."""

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'phone_number',
            'profile_picture',
            'bio',
            'user_type',
        ]


class PublicUserSerializer(serializers.ModelSerializer):
    """Serializer for public user info (for listing hosts, etc.)."""

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'profile_picture',
            'bio',
            'is_verified',
            'created_at',
        ]


class GuestIDSerializer(serializers.ModelSerializer):
    """Serializer for guest ID documents."""

    id_type_display = serializers.CharField(source='get_id_type_display', read_only=True)

    class Meta:
        model = GuestID
        fields = [
            'id',
            'id_type',
            'id_type_display',
            'uploaded_at',
            'is_verified',
            'is_primary',
        ]
        read_only_fields = ['id', 'uploaded_at', 'is_verified']


class GuestIDUploadConfirmSerializer(serializers.Serializer):
    """Serializer for confirming guest ID upload."""

    r2_key = serializers.CharField(max_length=500)
    id_type = serializers.ChoiceField(choices=GuestID.IDType.choices)
    set_as_primary = serializers.BooleanField(default=True)


class GuestIDUploadURLSerializer(serializers.Serializer):
    """Serializer for requesting a presigned upload URL."""

    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100, default='image/jpeg')
