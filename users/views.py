"""User views for ZCA BnB."""

from django.contrib.auth import get_user_model
from django.http import StreamingHttpResponse, Http404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import GuestID
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserProfileUpdateSerializer,
    GuestIDSerializer,
    GuestIDUploadConfirmSerializer,
    GuestIDUploadURLSerializer,
)
from .services import generate_upload_url, get_id_image, delete_id_from_r2, check_id_exists

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


class GuestIDViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing guest identification documents.
    Images are stored in private R2 bucket and accessed via proxy endpoint.
    """

    serializer_class = GuestIDSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GuestID.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='upload-url')
    def get_upload_url(self, request):
        """
        Get a presigned URL for uploading a guest ID image to R2.

        POST /api/users/guest-id/upload-url/
        {
            "filename": "my_id.jpg",
            "content_type": "image/jpeg"
        }

        Returns:
        {
            "upload_url": "https://...",
            "r2_key": "guest-ids/123/uuid.jpg"
        }
        """
        serializer = GuestIDUploadURLSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        upload_url, r2_key = generate_upload_url(
            user_id=request.user.id,
            filename=serializer.validated_data['filename'],
            content_type=serializer.validated_data.get('content_type', 'image/jpeg'),
        )

        return Response({
            'upload_url': upload_url,
            'r2_key': r2_key,
        })

    @action(detail=False, methods=['post'], url_path='confirm')
    def confirm_upload(self, request):
        """
        Confirm that an ID upload completed and save to database.

        POST /api/users/guest-id/confirm/
        {
            "r2_key": "guest-ids/123/uuid.jpg",
            "id_type": "national_id",
            "set_as_primary": true
        }
        """
        serializer = GuestIDUploadConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        r2_key = serializer.validated_data['r2_key']

        # Verify the file exists in R2
        if not check_id_exists(r2_key):
            return Response(
                {'detail': 'Upload not found. Please upload the file first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify the key belongs to this user
        expected_prefix = f"guest-ids/{request.user.id}/"
        if not r2_key.startswith(expected_prefix):
            return Response(
                {'detail': 'Invalid upload key.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Create the GuestID record
        guest_id = GuestID.objects.create(
            user=request.user,
            r2_key=r2_key,
            id_type=serializer.validated_data['id_type'],
            is_primary=serializer.validated_data.get('set_as_primary', True),
        )

        return Response(
            GuestIDSerializer(guest_id).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], url_path='image')
    def get_image(self, request, pk=None):
        """
        Proxy endpoint to retrieve guest ID image.
        Only the owner or hosts of bookings with this ID can access.

        GET /api/users/guest-id/{id}/image/
        """
        guest_id = self.get_object()

        # Check authorization
        # Owner can always view their own ID
        if guest_id.user != request.user:
            # Check if requester is a host with a booking using this ID
            from bookings.models import Booking
            is_host_with_booking = Booking.objects.filter(
                guest_id=guest_id,
                listing__host=request.user,
            ).exists()

            if not is_host_with_booking:
                return Response(
                    {'detail': 'You do not have permission to view this ID.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Get the image from R2
        body, content_type, content_length = get_id_image(guest_id.r2_key)

        if body is None:
            raise Http404('ID image not found')

        # Stream the image back to the client
        response = StreamingHttpResponse(
            body.iter_chunks(),
            content_type=content_type,
        )
        if content_length:
            response['Content-Length'] = content_length
        response['Cache-Control'] = 'private, max-age=3600'

        return response

    @action(detail=True, methods=['post'], url_path='set-primary')
    def set_primary(self, request, pk=None):
        """
        Set this ID as the primary/active ID.

        POST /api/users/guest-id/{id}/set-primary/
        """
        guest_id = self.get_object()
        guest_id.is_primary = True
        guest_id.save()

        return Response(GuestIDSerializer(guest_id).data)

    def perform_destroy(self, instance):
        """Delete the ID from both R2 and database."""
        try:
            delete_id_from_r2(instance.r2_key)
        except Exception:
            pass  # Continue even if R2 delete fails
        instance.delete()
