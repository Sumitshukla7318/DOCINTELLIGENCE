import pytest
from django.urls import reverse
from tests.factories import UserFactory


@pytest.mark.django_db
class TestProfile:

    def test_get_profile_success(self, auth_client, user):
        url = reverse("auth-profile")
        response = auth_client.get(url)

        assert response.status_code == 200
        assert response.data["email"] == user.email
        assert response.data["first_name"] == user.first_name
        assert "password" not in response.data

    def test_get_profile_requires_auth(self, api_client):
        url = reverse("auth-profile")
        response = api_client.get(url)
        assert response.status_code == 401

    def test_update_profile_success(self, auth_client):
        url = reverse("auth-profile")
        response = auth_client.patch(url, {
            "first_name": "Updated",
            "last_name": "Name",
        })
        assert response.status_code == 200
        assert response.data["first_name"] == "Updated"
        assert response.data["last_name"] == "Name"

    def test_cannot_update_email(self, auth_client, user):
        url = reverse("auth-profile")
        response = auth_client.patch(url, {"email": "newemail@example.com"})

        # Email stays unchanged
        assert response.status_code == 200
        assert response.data["email"] == user.email

    def test_full_name_property(self, auth_client):
        url = reverse("auth-profile")
        auth_client.patch(url, {"first_name": "John", "last_name": "Doe"})
        response = auth_client.get(url)
        assert response.data["full_name"] == "John Doe"


@pytest.mark.django_db
class TestChangePassword:

    def test_change_password_success(self, auth_client, user):
        url = reverse("auth-change-password")
        response = auth_client.post(url, {
            "old_password": "TestPass123!",
            "new_password": "NewStrongPass456!",
            "new_password_confirm": "NewStrongPass456!",
        })
        assert response.status_code == 200

        # Verify new password actually works
        user.refresh_from_db()
        assert user.check_password("NewStrongPass456!")

    def test_wrong_old_password_rejected(self, auth_client):
        url = reverse("auth-change-password")
        response = auth_client.post(url, {
            "old_password": "WrongOldPass!",
            "new_password": "NewStrongPass456!",
            "new_password_confirm": "NewStrongPass456!",
        })
        assert response.status_code == 400
        assert "incorrect" in str(response.data).lower()

    def test_new_password_mismatch_rejected(self, auth_client):
        url = reverse("auth-change-password")
        response = auth_client.post(url, {
            "old_password": "TestPass123!",
            "new_password": "NewPass456!",
            "new_password_confirm": "DifferentPass789!",
        })
        assert response.status_code == 400

    def test_weak_new_password_rejected(self, auth_client):
        url = reverse("auth-change-password")
        response = auth_client.post(url, {
            "old_password": "TestPass123!",
            "new_password": "123",
            "new_password_confirm": "123",
        })
        assert response.status_code == 400

    def test_change_password_requires_auth(self, api_client):
        url = reverse("auth-change-password")
        response = api_client.post(url, {
            "old_password": "TestPass123!",
            "new_password": "NewPass456!",
            "new_password_confirm": "NewPass456!",
        })
        assert response.status_code == 401