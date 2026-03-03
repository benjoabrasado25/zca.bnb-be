"""User URL configuration."""

from django.urls import path

from .views import (
    UserRegistrationView,
    UserProfileView,
    UserDetailView,
    BecomeHostView,
)

app_name = 'users'

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('<int:id>/', UserDetailView.as_view(), name='detail'),
    path('become-host/', BecomeHostView.as_view(), name='become-host'),
]
