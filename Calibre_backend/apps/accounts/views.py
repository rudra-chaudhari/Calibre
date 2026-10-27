from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    ChangePasswordSerializer,
    DeleteAccountSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserSerializer,
    UserUpdateSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    POST /auth/register/
    Request: {"email": "a@b.com", "password": "...", "name": "Rudra"}
    Flow: RegisterSerializer validates → register_user() creates user → issue token pair
    Response 201: {"user": {...}, "access": "...", "refresh": "..."}
    """
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    """
    POST /auth/login/
    Request: {"email": "...", "password": "..."}
    Response 200: {"access": "...", "refresh": "...", "user": {...}}
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer


class TokenRefreshView(TokenRefreshView):
    """
    POST /auth/token/refresh/
    Request: {"refresh": "..."}
    Response 200: {"access": "...", "refresh": "..."}
    """
    permission_classes = [AllowAny]


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    POST /auth/logout/
    Request: {"refresh": "<refresh token>"}
    Flow: parse token → blacklist() → 204
    Response: 204 on success
    """
    serializer = LogoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        token = RefreshToken(serializer.validated_data["refresh"])
        token.blacklist()
    except Exception:
        return Response(
            {"refresh": ["Invalid or expired token."]},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):
    """
    POST /auth/password/change/
    Request: {"old_password": "...", "new_password": "..."}
    Flow: ChangePasswordSerializer validates → set_password → save
    Response: 204
    """
    serializer = ChangePasswordSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(status=status.HTTP_204_NO_CONTENT)


class UserMeView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET /users/me/ - returns current user
    PATCH /users/me/ - update name, timezone, work_start, work_end
    DELETE /users/me/ - delete account (requires password)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserUpdateSerializer
        if self.request.method == "DELETE":
            return DeleteAccountSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
