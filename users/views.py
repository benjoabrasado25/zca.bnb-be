"""User views for ZCA BnB."""

from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserProfileUpdateSerializer,
)

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    """API view for user registration."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    """API view for retrieving and updating user profile."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserProfileUpdateSerializer
        return UserSerializer


class UserDetailView(generics.RetrieveAPIView):
    """API view for retrieving public user details."""

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'id'


class BecomeHostView(APIView):
    """API view for upgrading user to host status."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.user_type == User.UserType.HOST:
            return Response(
                {'detail': 'You are already a host.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.user_type == User.UserType.GUEST:
            user.user_type = User.UserType.BOTH
        else:
            user.user_type = User.UserType.HOST

        user.save()
        return Response(
            {'detail': 'You are now a host!', 'user_type': user.user_type},
            status=status.HTTP_200_OK
        )
