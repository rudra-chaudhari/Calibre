import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.common.models import Category
from apps.tasks.models import Task

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
