"""User URL configuration."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UserRegistrationView,
    UserProfileView,
    UserDetailView,
    BecomeHostView,
    GuestIDViewSet,
)

app_name = 'users'

router = DefaultRouter()
router.register(r'guest-id', GuestIDViewSet, basename='guest-id')

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('become-host/', BecomeHostView.as_view(), name='become-host'),
    path('', include(router.urls)),
    # Keep numeric ID route last to avoid conflicts
    path('<int:id>/', UserDetailView.as_view(), name='detail'),
]
