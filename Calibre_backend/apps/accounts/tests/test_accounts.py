import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user():
    return User.objects.create_user(
        email="test@example.com", password="TestPass123!", name="Test User"
    )


@pytest.mark.django_db
class TestRegister:
    def test_register_success(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": "new@example.com", "password": "StrongPass123!", "name": "New User"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == "new@example.com"

        user = User.objects.get(email="new@example.com")
        assert user.name == "New User"
        assert user.check_password("StrongPass123!") is True
        assert user.password != "StrongPass123!"

    def test_register_duplicate_email(self, api_client, test_user):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": "test@example.com", "password": "StrongPass123!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_duplicate_email_case_insensitive(self, api_client, test_user):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": "TEST@EXAMPLE.COM", "password": "StrongPass123!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_register_weak_password(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/", {"email": "new@example.com", "password": "123"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, test_user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, api_client, test_user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "WrongPass123!"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestUserMe:
    def test_get_user_me_without_token(self, api_client):
        response = api_client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_user_me_with_token(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "test@example.com"
        assert response.data["name"] == "Test User"

    def test_patch_user_me_valid(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.patch(
            "/api/v1/users/me/", {"name": "Updated Name", "timezone": "America/New_York"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"
        assert response.data["timezone"] == "America/New_York"

    def test_patch_user_me_invalid_timezone(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.patch("/api/v1/users/me/", {"timezone": "Invalid/Timezone"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "timezone" in response.data

    def test_patch_user_me_work_start_after_work_end(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.patch(
            "/api/v1/users/me/", {"work_start": "18:00", "work_end": "09:00"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogout:
    def test_logout_and_refresh_token_blacklisted(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        refresh_token = login_response.data["refresh"]
        access_token = login_response.data["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        logout_response = api_client.post(
            "/api/v1/auth/logout/", {"refresh": refresh_token}
        )
        assert logout_response.status_code == status.HTTP_204_NO_CONTENT

        refresh_response = api_client.post(
            "/api/v1/auth/token/refresh/", {"refresh": refresh_token}
        )
        assert refresh_response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestChangePassword:
    def test_change_password_success(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.post(
            "/api/v1/auth/password/change/",
            {"old_password": "TestPass123!", "new_password": "NewPass456!"},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        test_user.refresh_from_db()
        assert test_user.check_password("NewPass456!") is True

        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "NewPass456!"},
        )
        assert login_response.status_code == status.HTTP_200_OK

    def test_change_password_wrong_old_password(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.post(
            "/api/v1/auth/password/change/",
            {"old_password": "WrongPass123!", "new_password": "NewPass456!"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "old_password" in response.data


@pytest.mark.django_db
class TestDeleteAccount:
    def test_delete_account_success(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.delete(
            "/api/v1/users/me/", data={"password": "TestPass123!"}, format="json"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        assert not User.objects.filter(email="test@example.com").exists()

    def test_delete_account_wrong_password(self, api_client, test_user):
        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "TestPass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.delete(
            "/api/v1/users/me/", data={"password": "WrongPass123!"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

        assert User.objects.filter(email="test@example.com").exists()


@pytest.mark.django_db
class TestUserIsolation:
    def test_user_cannot_see_another_user(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="Pass123!", name="User 1"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="Pass123!", name="User 2"
        )

        login_response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "user1@example.com", "password": "Pass123!"},
        )
        token = login_response.data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get("/api/v1/users/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "user1@example.com"
        assert response.data["name"] == "User 1"
