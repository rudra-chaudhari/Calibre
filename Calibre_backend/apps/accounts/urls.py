from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    RegisterView,
    UserMeView,
    change_password_view,
    logout_view,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", logout_view, name="logout"),
    path("auth/password/change/", change_password_view, name="change_password"),
    path("users/me/", UserMeView.as_view(), name="user_me"),
]
