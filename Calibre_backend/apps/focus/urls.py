from rest_framework.routers import SimpleRouter

from .views import FocusSessionViewSet

router = SimpleRouter()
router.register("focus/sessions", FocusSessionViewSet, basename="focussession")

urlpatterns = router.urls
