import logging
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter,
)

from .serializers import (
    ChangePasswordSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Auth"],
        summary="Register a new user",
        description="Creates a new user account. Returns the user profile. Call `/login/` separately to get tokens.",
        request=UserRegistrationSerializer,
        responses={
            201: UserProfileSerializer,
            400: OpenApiResponse(description="Validation error — passwords don't match, email taken, etc."),
        },
        examples=[
            OpenApiExample(
                "Valid registration",
                value={
                    "email": "jane@example.com",
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "password": "StrongPass123!",
                    "password_confirm": "StrongPass123!",
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserProfileSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Logout",
        description=(
            "Blacklists the provided refresh token. "
            "The access token expires naturally based on its TTL (60 minutes). "
            "Safe to call multiple times — idempotent."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "refresh": {"type": "string", "description": "Your refresh token"}
                },
                "required": ["refresh"],
            }
        },
        responses={
            204: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Refresh token missing or invalid"),
        },
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception:
            return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user

    @extend_schema(
        tags=["Auth"],
        summary="Get my profile",
        description="Returns the authenticated user's profile information.",
        responses={200: UserProfileSerializer},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=["Auth"],
        summary="Update my profile",
        description="Updates `first_name` and/or `last_name`. Email cannot be changed.",
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
        examples=[
            OpenApiExample(
                "Update name",
                value={"first_name": "Jane", "last_name": "Smith"},
                request_only=True,
            )
        ],
    )
    def patch(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Auth"],
        summary="Change password",
        description="Allows an authenticated user to change their own password. Requires current password for verification.",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description="Old password incorrect or new passwords don't match"),
        },
        examples=[
            OpenApiExample(
                "Change password",
                value={
                    "old_password": "OldPass123!",
                    "new_password": "NewPass456!",
                    "new_password_confirm": "NewPass456!",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password", "updated_at"])
        return Response({"detail": "Password changed successfully."})