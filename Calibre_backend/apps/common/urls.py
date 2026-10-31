from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, health_view

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")

urlpatterns = [
    path("health/", health_view, name="health"),
] + router.urls
