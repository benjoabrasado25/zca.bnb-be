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
    """API view for applying to become a host (requires admin approval)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.utils import timezone

        user = request.user

        # Already an approved host
        if user.is_host:
            return Response(
                {'detail': 'You are already an approved host.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Already pending approval
        if user.host_status == User.HostStatus.PENDING:
            return Response(
                {'detail': 'Your host application is pending approval.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Submit application for admin approval
        user.user_type = User.UserType.HOST
        user.host_status = User.HostStatus.PENDING
        user.host_application_date = timezone.now()
        user.save()

        return Response(
            {
                'detail': 'Your host application has been submitted and is pending admin approval.',
                'host_status': user.host_status
            },
            status=status.HTTP_200_OK
        )
