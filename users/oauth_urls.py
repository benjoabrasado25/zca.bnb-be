"""OAuth URL configuration for Google Sign-In."""

from django.urls import path
from .oauth_views import GoogleLogin, GoogleLoginCallback

urlpatterns = [
    path('login/', GoogleLogin.as_view(), name='google_login'),
    path('callback/', GoogleLoginCallback.as_view(), name='google_callback'),
]
