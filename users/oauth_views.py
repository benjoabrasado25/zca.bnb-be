"""OAuth views for Google Sign-In."""

import os
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from rest_framework_simplejwt.tokens import RefreshToken
import requests


class GoogleLogin(SocialLoginView):
    """
    Google OAuth2 login view.

    POST with either:
    - access_token: Google access token from frontend OAuth flow
    - code: Authorization code from Google OAuth redirect
    """
    adapter_class = GoogleOAuth2Adapter
    callback_url = os.environ.get('GOOGLE_CALLBACK_URL', 'http://localhost:5173/auth/google/callback')
    client_class = OAuth2Client
    permission_classes = [AllowAny]


class GoogleLoginCallback(APIView):
    """
    Handle Google OAuth callback and exchange code for tokens.
    This is called by the frontend after Google redirects back with a code.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """Exchange Google authorization code for JWT tokens."""
        code = request.data.get('code')

        if not code:
            return Response(
                {'error': 'Authorization code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Exchange code for Google tokens
        google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        redirect_uri = os.environ.get('GOOGLE_CALLBACK_URL', 'http://localhost:5173/auth/google/callback')

        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': google_client_id,
                'client_secret': google_client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }
        )

        if token_response.status_code != 200:
            return Response(
                {'error': 'Failed to exchange code for tokens', 'details': token_response.json()},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_data = token_response.json()
        access_token = token_data.get('access_token')

        # Get user info from Google
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )

        if user_info_response.status_code != 200:
            return Response(
                {'error': 'Failed to get user info from Google'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_info = user_info_response.json()
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        picture = user_info.get('picture', '')

        # Get or create user
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'is_verified': True,
            }
        )

        if created:
            # Set unusable password for OAuth users
            user.set_unusable_password()
            user.save()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'username': user.username,
                'profile_picture': picture,
            }
        })


class GoogleAuthURL(APIView):
    """Return the Google OAuth URL for frontend to redirect to."""
    permission_classes = [AllowAny]

    def get(self, request):
        google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
        redirect_uri = os.environ.get('GOOGLE_CALLBACK_URL', 'http://localhost:5173/auth/google/callback')

        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={google_client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=openid%20email%20profile&"
            f"access_type=online"
        )

        return Response({'auth_url': auth_url})
