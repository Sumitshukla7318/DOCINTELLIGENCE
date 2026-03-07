import pytest
from django.urls import reverse
from tests.factories import UserFactory


@pytest.mark.django_db
class TestRegister:

    def test_register_success(self, api_client):
        url = reverse("auth-register")
        payload = {
            "email": "newuser@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = api_client.post(url, payload)
        assert response.status_code == 201
        assert response.data["email"] == "newuser@example.com"
        assert "password" not in response.data  # Never expose password

    def test_register_password_mismatch(self, api_client):
        url = reverse("auth-register")
        payload = {
            "email": "user@example.com",
            "password": "StrongPass123!",
            "password_confirm": "DifferentPass!",
        }
        response = api_client.post(url, payload)
        assert response.status_code == 400
        assert "Passwords do not match" in str(response.data)

    def test_register_duplicate_email(self, db, api_client):
        UserFactory(email="taken@example.com")
        url = reverse("auth-register")
        payload = {
            "email": "taken@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
        }
        response = api_client.post(url, payload)
        assert response.status_code == 400

    def test_register_weak_password(self, api_client):
        url = reverse("auth-register")
        payload = {
            "email": "user@example.com",
            "password": "123",
            "password_confirm": "123",
        }
        response = api_client.post(url, payload)
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, db, api_client):
        user = UserFactory(email="login@example.com")
        url = reverse("auth-login")
        response = api_client.post(url, {
            "email": "login@example.com",
            "password": "TestPass123!",
        })
        assert response.status_code == 200
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data             # Our custom token serializer
        assert response.data["user"]["email"] == "login@example.com"

    def test_login_wrong_password(self, db, api_client):
        UserFactory(email="user@example.com")
        url = reverse("auth-login")
        response = api_client.post(url, {
            "email": "user@example.com",
            "password": "WrongPassword!",
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        url = reverse("auth-login")
        response = api_client.post(url, {
            "email": "ghost@example.com",
            "password": "AnyPassword123!",
        })
        assert response.status_code == 401


@pytest.mark.django_db
class TestLogout:

    def test_logout_success(self, auth_client, user):
        # Get a refresh token first
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        url = reverse("auth-logout")
        response = auth_client.post(url, {"refresh": str(refresh)})
        assert response.status_code == 204

    def test_logout_blacklisted_token_cannot_refresh(self, auth_client, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        # Logout — blacklist the token
        auth_client.post(reverse("auth-logout"), {"refresh": str(refresh)})

        # Try to refresh with the blacklisted token
        response = auth_client.post(reverse("auth-token-refresh"), {"refresh": str(refresh)})
        assert response.status_code == 401

    def test_logout_requires_auth(self, api_client):
        url = reverse("auth-logout")
        response = api_client.post(url, {"refresh": "sometoken"})
        assert response.status_code == 401