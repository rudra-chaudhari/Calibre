import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.common.services import seed_default_categories

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(api_client):
    user = User.objects.create_user(
        email="test@example.com", password="TestPass123!", name="Test User"
    )
    return user


@pytest.fixture
def authenticated_client(api_client, test_user):
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "test@example.com", "password": "TestPass123!"},
    )
    token = response.data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.mark.django_db
class TestHealth:
    def test_health_without_token(self, api_client):
        response = api_client.get("/api/v1/health/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "ok"
        assert response.data["db"] == "ok"
        assert "time" in response.data


@pytest.mark.django_db
class TestCategoriesAuth:
    def test_categories_without_token(self, api_client):
        response = api_client.get("/api/v1/categories/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestCreateCategory:
    def test_create_category_success(self, authenticated_client, test_user):
        response = authenticated_client.post(
            "/api/v1/categories/", {"name": "Test Category", "color": "#FF0000"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Test Category"
        assert response.data["color"] == "#FF0000"
        assert "user" not in response.data  # user field not exposed

        category = Category.objects.get(id=response.data["id"])
        assert category.user == test_user

    def test_create_category_with_user_field_ignored(self, authenticated_client, test_user):
        other_user = User.objects.create_user(
            email="other@example.com", password="TestPass123!"
        )
        response = authenticated_client.post(
            "/api/v1/categories/",
            {"name": "Test Category", "color": "#FF0000", "user": other_user.id},
        )
        assert response.status_code == status.HTTP_201_CREATED

        category = Category.objects.get(id=response.data["id"])
        assert category.user == test_user  # still created under requesting user


@pytest.mark.django_db
class TestCategoryValidation:
    def test_duplicate_name_same_user(self, authenticated_client, test_user):
        Category.objects.create(user=test_user, name="Work", color="#000000")
        response = authenticated_client.post(
            "/api/v1/categories/", {"name": "Work", "color": "#FF0000"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_duplicate_name_case_insensitive(self, authenticated_client, test_user):
        Category.objects.create(user=test_user, name="Work", color="#000000")
        response = authenticated_client.post(
            "/api/v1/categories/", {"name": "work", "color": "#FF0000"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_duplicate_name_different_user(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        Category.objects.create(user=user1, name="Work", color="#000000")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.post("/api/v1/categories/", {"name": "Work", "color": "#FF0000"})
        assert response.status_code == status.HTTP_201_CREATED

    def test_invalid_color(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/categories/", {"name": "Test", "color": "invalid"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "color" in response.data

    def test_empty_name(self, authenticated_client):
        response = authenticated_client.post(
            "/api/v1/categories/", {"name": "   ", "color": "#FF0000"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data


@pytest.mark.django_db
class TestListCategories:
    def test_list_returns_only_user_categories(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        Category.objects.create(user=user1, name="Cat1", color="#000000")
        Category.objects.create(user=user2, name="Cat2", color="#000000")

        token = api_client.post("/api/v1/auth/login/", {"email": "user1@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get("/api/v1/categories/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["name"] == "Cat1"

    def test_list_is_plain_array(self, authenticated_client, test_user):
        Category.objects.create(user=test_user, name="Cat1", color="#000000")
        response = authenticated_client.get("/api/v1/categories/")
        assert isinstance(response.data, list)
        assert "count" not in response.data
        assert "results" not in response.data


@pytest.mark.django_db
class TestCategoryIsolation:
    def test_other_user_category_returns_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        cat = Category.objects.create(user=user1, name="Cat1", color="#000000")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.get(f"/api/v1/categories/{cat.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_other_user_category_patch_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        cat = Category.objects.create(user=user1, name="Cat1", color="#000000")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.patch(f"/api/v1/categories/{cat.id}/", {"name": "New Name"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        cat.refresh_from_db()
        assert cat.name == "Cat1"  # unchanged

    def test_other_user_category_delete_404(self, api_client):
        user1 = User.objects.create_user(
            email="user1@example.com", password="TestPass123!"
        )
        user2 = User.objects.create_user(
            email="user2@example.com", password="TestPass123!"
        )
        cat = Category.objects.create(user=user1, name="Cat1", color="#000000")

        token = api_client.post("/api/v1/auth/login/", {"email": "user2@example.com", "password": "TestPass123!"}).data["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = api_client.delete(f"/api/v1/categories/{cat.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert Category.objects.filter(id=cat.id).exists()  # still exists


@pytest.mark.django_db
class TestUpdateCategory:
    def test_patch_rename_success(self, authenticated_client, test_user):
        cat = Category.objects.create(user=test_user, name="Old Name", color="#000000")
        response = authenticated_client.patch(f"/api/v1/categories/{cat.id}/", {"name": "New Name"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "New Name"

    def test_patch_rename_to_existing_name(self, authenticated_client, test_user):
        Category.objects.create(user=test_user, name="Existing", color="#000000")
        cat = Category.objects.create(user=test_user, name="Other", color="#000000")
        response = authenticated_client.patch(f"/api/v1/categories/{cat.id}/", {"name": "Existing"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data


@pytest.mark.django_db
class TestDeleteCategory:
    def test_delete_success(self, authenticated_client, test_user):
        cat = Category.objects.create(user=test_user, name="To Delete", color="#000000")
        response = authenticated_client.delete(f"/api/v1/categories/{cat.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(id=cat.id).exists()


@pytest.mark.django_db
class TestSeedDefaultCategories:
    def test_seed_creates_8_categories(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        seed_default_categories(user)
        assert Category.objects.filter(user=user).count() == 8
        assert Category.objects.filter(user=user, is_default=True).count() == 8

    def test_seed_idempotent(self):
        user = User.objects.create_user(email="test@example.com", password="TestPass123!")
        seed_default_categories(user)
        seed_default_categories(user)
        assert Category.objects.filter(user=user).count() == 8


@pytest.mark.django_db
class TestRegisterSeedsCategories:
    def test_register_creates_default_categories(self, api_client):
        response = api_client.post(
            "/api/v1/auth/register/",
            {"email": "new@example.com", "password": "StrongPass123!", "name": "New User"},
        )
        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="new@example.com")
        assert Category.objects.filter(user=user).count() == 8
        assert Category.objects.filter(user=user, is_default=True).count() == 8
